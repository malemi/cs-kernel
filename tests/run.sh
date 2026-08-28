#!/usr/bin/env bash
# Semantic gates for the cs kernel — the only tests that matter.
# Run from anywhere: resolves the repo root itself. CI runs exactly this.
#
#   1. grep gate           zero company literals in the package (charter §)
#   1b. slot contract      company/ slots say what to write, never what one
#                          company does (the wordlist cannot see that class)
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
# The BARE BRAND, separately. Until 2026-08-24 the wordlist carried only the
# mailbox DOMAIN (`mrcall.ai`), so the brand on its own walked straight past it:
# a project template shipped a whole page of one company's internal API access,
# another named that company's engine service-user home, and both greped clean.
# The brand cannot simply be added to the wordlist above, because the charter
# blesses it where it names shared infrastructure the kernel drives (the
# mrcall-desktop engine, the mrcall-tracking adapter id, the
# mrcall.search_businesses RPC method) — ~50 lines that are identical for every
# clone and are not clone data. Those FORMS are blessed by pattern here rather
# than line by line in the registry: copying 50 exact lines into
# reviewed_literals.txt would bury the handful of real proposals in them, and
# every one of the 50 would go stale on the next reword. Anything else carrying
# the brand — `<brand>-agent`, `/api/<brand>/`, `~<brand>d/`, a bare possessive
# — survives the strip and reaches the operator as a proposal like any other.
BRAND_HITS="$(grep -rEin --exclude-dir=__pycache__ 'mrcall' cs/ || true)"
ALL_HITS="$(printf '%s\n%s\n' "$CI_HITS" "$CS_HITS")"
if ! ALL_HITS="$ALL_HITS" BRAND_HITS="$BRAND_HITS" \
     REVIEWED_LITERALS="$ROOT/tests/reviewed_literals.txt" python3 - <<'PYEOF'
import os
import re

hits_raw = os.environ.get("ALL_HITS", "")
brand_raw = os.environ.get("BRAND_HITS", "")
reviewed_path = os.environ["REVIEWED_LITERALS"]

# Shared-infrastructure forms of the platform brand, blessed by the charter
# (CLAUDE.md rule 1): the engine, the producer adapter id, the CRM RPC method.
BLESSED_BRAND = re.compile(
    r"mrcall[-_]?desktop|mrcall[-_]?tracking|mrcall\.search_businesses", re.I
)


def _split(line):
    path, _, rest = line.partition(":")
    _lineno, _, content = rest.partition(":")
    return path, content


hits = []
seen = set()


def _add(path, content):
    # One line can match two patterns; report it once.
    key = (path, content.strip())
    if key not in seen:
        seen.add(key)
        hits.append((path, content))


for line in hits_raw.splitlines():
    if line:
        _add(*_split(line))

for line in brand_raw.splitlines():
    if not line:
        continue
    path, content = _split(line)
    # Strip every blessed form, then ask whether the brand is STILL there.
    if re.search("mrcall", BLESSED_BRAND.sub("", content), re.I):
        _add(path, content)

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

step "1b. company slot contract: cs/templates/project/company/ is instructions, not content"
# The slots under company/ are the ONE directory whose stamped content is meant
# to be replaced by each clone's own operator. That made them the blind spot:
# they carried the mother clone's real operational facts — a named weekday
# cutover, a legacy cron to retire, a dated "verified live on production" page
# of one company's internal API — and every one of them got stamped into every
# other company's clone as if it were true there. No wordlist catches that
# class: "the Friday cutover" contains no brand, no domain and no slug.
#
# So the gate holds the SHAPE instead. A slot is an instruction to its operator,
# and an instruction has two properties a leaked fact does not:
#   (A) it says what to write, under a literal "## What to write here" heading —
#       a file that is content rather than instructions simply does not have one;
#   (B) it carries no dated claim, no named weekday, no URL, no mail address, no
#       API path and no other user's home — the shapes an operational fact takes
#       when it is true of exactly one company on exactly one day.
# README.md.j2 is the directory index, not a slot, so (A) does not apply to it.
# Neither test is a proof of genericity; both are cheap, and both would have
# failed loudly on what shipped.
if ! python3 - "$ROOT" <<'PYEOF'
import re
import sys
from pathlib import Path

slot_dir = Path(sys.argv[1]) / "cs" / "templates" / "project" / "company"
MARKER = "## What to write here"
NOT_INDEX = {"README.md.j2"}

FACT_SHAPES = [
    (re.compile(r"\b20\d\d-\d\d-\d\d\b"), "a dated claim"),
    (re.compile(r"\b(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day\b"), "a named weekday"),
    (re.compile(r"https?://"), "a URL"),
    (re.compile(r"[\w.%+-]+@[\w-]+\.[A-Za-z]{2,}"), "a mail address"),
    (re.compile(r"/api/"), "an API path"),
    (re.compile(r"(?<![\w~])~[A-Za-z][\w.-]*/|/home/|/Users/"), "another user's home"),
]

problems = []
slots = sorted(slot_dir.glob("*.j2"))
if not slots:
    print("FAIL: no slot templates found under %s" % slot_dir)
    raise SystemExit(1)

for slot in slots:
    text = slot.read_text()
    rel = slot.relative_to(slot_dir.parents[3])
    if slot.name not in NOT_INDEX and MARKER not in text:
        problems.append(
            "%s: no '%s' section — a slot must tell its operator what belongs "
            "in it and why" % (rel, MARKER)
        )
    for lineno, line in enumerate(text.splitlines(), 1):
        for pattern, what in FACT_SHAPES:
            if pattern.search(line):
                problems.append(
                    "%s:%d: %s — that is one company's fact, not an instruction: "
                    "%s" % (rel, lineno, what, line.strip())
                )

if problems:
    for p in problems:
        print("  " + p)
    print(
        "FAIL: %d company-slot violation(s). A slot under company/ is stamped "
        "into EVERY clone: it may describe what to write, never what one "
        "company happens to do." % len(problems)
    )
    raise SystemExit(1)

print("OK: %d company slots are instructions (no dated/company facts)" % len(slots))
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
for v in init update login plan whoami rpc thread contacted unanswered handled escalated tasks business dossier ask draft-reply draft-delete review catchup drive accounts config chat campaign project; do
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

step "17. deny-enumeration gate (every command-text spelling of a denied surface)"
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
# equality against the 48 deny entries + 4 keeps. `handled` is in that list not
# because it sends, but because it SILENCES: it declares a contact resolved
# off-email, and a tick reading untrusted inbound must never be talked into it.
# `escalated` is there for the sharper version of the same reason: it asserts
# that a named HUMAN is personally handling a contact, which no machine can
# claim on that human's behalf, and which the review then repeats back to him
# as "you are on this one". `draft-delete` and `rpc drafts.discard` are the two
# halves of retiring a draft — Gmail's copy and the engine's — and the tick now
# COMPUTES the verdict that would tempt it to use them: a draft the conversation
# has moved past is a prepared answer no human has seen yet, so the tick reports
# it and the operator retires it by name. `rpc drafts.discard` is spelled out
# for the same reason as `rpc chat`: settings.json allows the broad `cs rpc:*`,
# and the engine's discard DELETES the row — there is no Trash to recover from.
#
# The wrapper's deny list is no longer a fixed text, so this gate reads the
# RENDER and not the template source: a clone may name executables of its own
# in `[local_scripts] cron_denied`, and the wrapper expands each into every
# interpreter and both path forms. Two renders are checked, and the EMPTY one
# is not an afterthought — declaring nothing is what almost every clone does,
# and it must produce exactly the kernel's own list, byte for byte. The second
# render passes one invented path and asserts all fourteen entries appear, in
# order, in the right place. The sample is invented on purpose: a gate that
# named a real clone's script would be that clone's data living in shared
# code, and would pass while the mechanism underneath it was broken.
CRON_TPL="$ROOT/cs/templates/project/bin/cs_operator_cron.sh.j2"
SETTINGS_TPL="$ROOT/cs/templates/project/.claude/settings.json.j2"
if ! "$VENV/bin/python" - "$SETTINGS_TPL" "$CRON_TPL" <<'PYEOF'
import json, re, sys
from pathlib import Path

from cs import project_init

SETTINGS_PATH, CRON_PATH = sys.argv[1], sys.argv[2]

SPELLINGS = [
    ".venv/bin/python -m cs",
    ".venv/bin/python3 -m cs",
    ".venv/bin/cs",
    "python -m cs",
    "python3 -m cs",
    "cs",
]
VERBS = [
    "chat", "rpc chat", "campaign send-draft", "rpc settings.update",
    "handled", "escalated", "draft-delete", "rpc drafts.discard",
]

# The expansion a clone-local executable gets, rebuilt here INDEPENDENTLY of
# the template rather than shared with it through a helper: a gate that
# imported the same expansion it is checking would agree with the template
# about a wrong answer. Interpreter-less first, because a script with a
# shebang and the executable bit needs no interpreter word at all — the
# spelling that is easiest to forget and cheapest to walk through.
INTERPRETERS = ["", ".venv/bin/python", ".venv/bin/python3",
                "python", "python3", "bash", "sh"]

# Invented, and it must stay invented. No real clone's filename belongs in
# kernel code, not even as a test fixture: the mechanism is what is gated.
SAMPLE_SCRIPT = "bin/example_tool.py"

KEEPS = ["Write", "Edit", "Bash(rm:*)", "Bash(git push:*)"]


def local_tokens(script):
    out = []
    for form in (script, "./" + script):
        for interp in INTERPRETERS:
            cmd = "%s %s" % (interp, form) if interp else form
            out.append("Bash(%s:*)" % cmd)
    return out


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

cron_tpl_path = Path(CRON_PATH)
tpl_root = cron_tpl_path.parent.parent  # cs/templates/project/
env = project_init.build_jinja_env(tpl_root)
tpl = env.get_template("bin/cs_operator_cron.sh.j2")

# The full variable set the whole tree renders against, so the wrapper is
# rendered exactly the way `cs init`/`cs update` render it.
BASE = dict(
    company_name="Acme Corp", company_display_name="Acme",
    company_from_name="Acme Support", company_slug="acme",
    company_prog_name="acme-cs", email_address="support@acme.example",
    operator_voice=project_init.DEFAULT_OPERATOR_VOICE,
)


def render_tokens(local_scripts):
    """The --disallowed-tools argument list of an actual render."""
    text = tpl.render(local_scripts_cron_denied=local_scripts, **BASE)
    lines = text.splitlines(keepends=True)
    start = next((i for i, l in enumerate(lines) if "--disallowed-tools" in l), None)
    if start is None or lines[start].strip().startswith("#"):
        return None, "--disallowed-tools flag line missing or commented out"
    end = next((i for i in range(start + 1, len(lines)) if '>>"$LOG"' in lines[i]), None)
    if end is None:
        return None, 'closing >>"$LOG" line not found after --disallowed-tools'
    tokens = []
    for line in lines[start:end]:
        if line.strip().startswith("#"):
            continue
        tokens.extend(re.findall(r'"([^"]*)"', line))
    return tokens, None


def compare(label, tokens, expected):
    if tokens == expected:
        return
    problems.append(
        "FAIL: cron --disallowed-tools token list mismatch (%s: got %d, expected %d)"
        % (label, len(tokens), len(expected))
    )
    missing = [t for t in expected if t not in tokens]
    extra = [t for t in tokens if t not in expected]
    if missing:
        problems.append("FAIL:   missing: %s" % ", ".join(missing))
    if extra:
        problems.append("FAIL:   extra:   %s" % ", ".join(extra))
    if not missing and not extra:
        problems.append("FAIL:   same members present, but order differs")


kernel_expected = ["Bash(%s %s:*)" % (sp, v) for v in VERBS for sp in SPELLINGS]

try:
    # (a) The normal case. A clone that names no executables of its own — which
    # is nearly all of them — gets precisely the kernel's own list. This is a
    # first-class path, not a degraded one: if declaring nothing ever started
    # emitting a stray token, every clone would inherit it.
    empty_tokens, err = render_tokens([])
    if err:
        problems.append("FAIL: empty-manifest render — %s" % err)
    else:
        compare("no local scripts declared", empty_tokens, kernel_expected + KEEPS)

    # (b) One declared executable expands into all fourteen spellings, between
    # the cs verbs and the keeps. The interpreter-less pair is the point of the
    # whole gate: `bin/example_tool.py` with a shebang and mode 0755 runs with
    # no interpreter word in front of it and matches no `python …` rule.
    one_tokens, err = render_tokens([SAMPLE_SCRIPT])
    if err:
        problems.append("FAIL: one-script render — %s" % err)
    else:
        compare(
            "one local script declared",
            one_tokens,
            kernel_expected + local_tokens(SAMPLE_SCRIPT) + KEEPS,
        )

    # (c) The declaration reaches the render THROUGH manifest.toml's own key,
    # not only through a variable a test happens to pass. `[local_scripts]
    # cron_denied` is where an operator writes it, and a mechanism that only
    # worked when the test set the variable by hand would ship broken.
    from_manifest = project_init.normalize_local_scripts(["./" + SAMPLE_SCRIPT, "", SAMPLE_SCRIPT])
    if from_manifest != [SAMPLE_SCRIPT]:
        problems.append(
            "FAIL: [local_scripts] cron_denied normalisation — expected %r, got %r"
            % ([SAMPLE_SCRIPT], from_manifest)
        )
except Exception as exc:  # a render error must fail the gate, never crash it
    problems.append("FAIL: cron template render raised %s: %s" % (type(exc).__name__, exc))

if problems:
    for p in problems:
        print(p)
    sys.exit(1)

print(
    "OK: settings.json deny membership + allow purity; cron --disallowed-tools "
    "order verified on both renders (%d entries with no local scripts, %d with one)"
    % (len(kernel_expected) + len(KEEPS),
       len(kernel_expected) + len(local_tokens(SAMPLE_SCRIPT)) + len(KEEPS))
)
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

step "30. handled out of band — dated suppression, and every surface obeys it"
# 2026-08: a customer wrote on 17 July, the owner TELEPHONED him and resolved it,
# and because a phone call leaves no trace in Gmail Sent (the dedup ground truth)
# every tick for a MONTH re-discovered the thread and told the owner to write to
# him. Guards: an inbound before the handled moment is not open work, a NEWER one
# re-opens the contact, the held-back senders are still REPORTED (an invisible
# filter reads as a bug), the record is idempotent and undoable, recording closes
# the contact's open engine tasks with actor="human" reading `id` from
# tasks.list (NOT the `task_id` tasks.complete wants), a mistyped address is a
# clean refusal, and sweep() actually feeds the ledger into the open-logic.
if "$VENV/bin/python" "$ROOT/tests/test_handled.py"; then echo "OK"; else echo "FAIL: out-of-band handling regressed"; FAIL=1; fi

step "31. cs config — resolved value + provenance, duplicate flag, no secret printed"
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

step "32. [campaigns].excluded_campaign holds MORE THAN ONE campaign"
# A clone finished two related campaigns and the field held one string matched
# with ==; the second kept reaching the general operator for a month, and the
# engine offers no campaign.close to fall back on. Guards: one bare name still
# works (the old shape, so no stamped clone breaks), several names all exclude,
# empty/whitespace/"," exclude NOTHING (never an empty-named member, which would
# match a blank campaign lookup), and a name sharing a PREFIX with an excluded
# one is NOT excluded — at pending() and at both contact-level gates. Plus:
# cs config prints several names readably.
if "$VENV/bin/python" "$ROOT/tests/test_excluded_campaigns.py"; then echo "OK"; else echo "FAIL: excluded-campaign list regressed"; FAIL=1; fi

step "33. a finished campaign delivers NOTHING, on any path"
# 2026-08-23: a tick was handed 26 send_sms items for a campaign that ended on
# 31 July. Its pack said so twice — status never flipped, dates = "2026-07-22..31"
# — and nothing read either field. The SMS would have told 26 real customers
# their number changes at a moment three weeks past; CS_PAUSE caught it. Guards:
# status is active|done and an unknown value refuses at LOAD; the new typed
# ends_on refuses delivery past its date EVEN while status says active (the case
# that bit), takes "never" for an open-ended campaign, and refuses any
# unparseable value rather than reading it as "no limit"; a pack with NO ends_on
# still delivers for ever (the onboarding loop) and is reported instead; all
# five delivery paths refuse — send_first / send_reminder / send_sms /
# send_draft / queue_draft, each reachable by contact id WITHOUT pending(); and
# the refusal is visible everywhere (reason + date, held counts), with
# handle_reply still coming through because a reply is not a delivery.
if "$VENV/bin/python" "$ROOT/tests/test_campaign_finished.py"; then echo "OK"; else echo "FAIL: a finished campaign can still deliver"; FAIL=1; fi

step "34. escalated to a human — still open, still visible, nobody else writes"
# The owner was mid-conversation with two customers, writing to them himself.
# Nothing in Gmail Sent said so, so the sweep counted both as unanswered work
# and the two-hourly operator — which answers customers itself — kept preparing
# a second reply. The only states on offer were "resolved" (a lie) and
# "nothing" (the collision). Guards: an escalated sender leaves the open list
# and comes back in its OWN bucket with owner, reason and the AGE of the
# takeover; a NEWER inbound does NOT release it (the deliberate asymmetry with
# `handled`, whose expiry would re-arm the collision on the very event that
# causes it); `handled` wins and clears it; the verb is dry-run until --commit
# in both directions and NEVER touches the engine (the task stays open — the
# work is not done); refusals write nothing; and every surface that hides the
# contact also prints it — unanswered, review, dossier (verdict STOP) — while
# no automated outbound reaches them: the producer worklist skips with a
# counted reason and the campaign senders + pending() refuse on their own.
if "$VENV/bin/python" "$ROOT/tests/test_escalated.py"; then echo "OK"; else echo "FAIL: escalated-to-a-human regressed"; FAIL=1; fi

step "35. the ignore list matches patterns, and only what a pattern should reach"
# Seven rows of one sweep were the SAME bounce: the provider's mail daemon
# answers from a rotating host, so an exact-match ignore list is stale on the
# next bounce and the operator is handed a robot to answer. Guards: one
# `mail-daemon@*` catches every rotation, in every bucket (never resurfacing as
# `handled` or `escalated`); a list with NO wildcard produces the identical set
# it always did, with no prefix effects; no daemon pattern reaches an address a
# human writes from; and Sent-anchoring is untouched.
if "$VENV/bin/python" "$ROOT/tests/test_system_sender_patterns.py"; then echo "OK"; else echo "FAIL: ignore-list pattern matching regressed"; FAIL=1; fi

step "36. /cs-review — the ONE command, and the kill-switch is state, not news"
# Measured against a real morning: the bootstrap answered three of the eight
# questions a returning operator has, and surfaced the kill-switch only BY
# ACCIDENT (the cron log tail happened to be all `paused … skip`), framed it as
# a fault, and offered clearing it as the FIRST next step — without mentioning
# that the triage mode is `send`, i.e. proposing to resume real sending without
# saying it was a sending mode. Guards: the steps that answer the rest exist
# (`cs config` for what is in force, `cs --version` for the pin actually
# installed, `git log` for what changed, the 45-day CRM-grouped sweep, the
# owner-actions digest); the greeting names the pause exactly ONCE, as the
# operator's own decision, with no alarm word, and neither the file nor the
# closing options offer to lift it; nothing that would send him elsewhere is
# collapsed into a count (per-draft uids, out-of-band records); plain campaign
# outcomes ARE counted (31 identical rows earned nothing); and the read-only
# verbs it runs are allowed, so the one command does not stop on a prompt.
if "$VENV/bin/python" "$ROOT/tests/test_review_bootstrap.py"; then echo "OK"; else echo "FAIL: the review bootstrap regressed"; FAIL=1; fi

step "37. unanswered reads CONVERSATIONS, and asks the engine what a message IS"
# The address-keyed sweep was wrong four ways at once on the live queue: a
# colleague only Cc'd on an answered thread sat open 28 days; a later helpful
# reply closed an older untouched conversation; our OWN auto-acknowledgement,
# in Gmail Sent 17 seconds after four product questions, counted as an answer
# and hid them for 70 days; and a customer's "thank you" headed the queue as
# open work. Guards, in order: the thread key closes a participant the reply
# was not addressed to; a new thread does not close an old one; an outbound the
# ENGINE flags automatic does not close a conversation, while an ABSENT engine
# view degrades to exactly the old behaviour; a courtesy after our answer is
# re-labelled and still printed; `automatic` is the engine's call and never the
# kernel's; an autoresponder on one thread cannot bury a real request on
# another; and an operator's own `handled` record still outranks all of it.
if "$VENV/bin/python" "$ROOT/tests/test_unanswered_threads.py"; then echo "OK"; else echo "FAIL: the conversation-level sweep regressed"; FAIL=1; fi

step "38. the engine is authoritative — the charter rule reaches every clone"
# "se l'engine non fa il suo lavoro, si corregge l'engine, non si rappezza
# altro" (operator, 2026-08-26). The rule is only worth writing down if a CLONE
# inherits it, so it must be in the rendered project CLAUDE.md and not only in
# the kernel's own charter. Both files are checked, plus the measured exception
# that keeps it honest (Gmail Sent, not the engine archive, is dedup truth).
# The phrases are matched against the file with all whitespace collapsed to
# single spaces, NOT line by line. A prose rule wraps wherever the paragraph
# happens to end, and a line-bound grep reports the rule as MISSING the moment
# somebody reflows the sentence — which is what happened on 2026-08-27, when a
# doc consolidation split "fix the engine" across a line break and turned this
# gate red while the rule itself was untouched. A gate that a rewrap can defeat
# does not measure whether the rule is written down.
GATE38=0
for f in "$ROOT/CLAUDE.md" "$ROOT/cs/templates/project/CLAUDE.md.j2"; do
  flat=$(tr '\n' ' ' < "$f" | tr -s '[:space:]' ' ')
  case "$(printf '%s' "$flat" | tr '[:upper:]' '[:lower:]')" in
    *authoritative*) ;;
    *) echo "MISSING: engine-authority rule in $f"; GATE38=1 ;;
  esac
  case "$(printf '%s' "$flat" | tr '[:upper:]' '[:lower:]')" in
    *"fix the engine"*) ;;
    *) echo "MISSING: 'fix the engine' in $f"; GATE38=1 ;;
  esac
  case "$(printf '%s' "$flat" | tr '[:upper:]' '[:lower:]')" in
    *sent*) ;;
    *) echo "MISSING: the dedup-truth exception in $f"; GATE38=1 ;;
  esac
done
if [ "$GATE38" -eq 0 ]; then echo "OK"; else echo "FAIL: the engine-authority rule is not inherited by clones"; FAIL=1; fi

step "39. a closing courtesy is the ENGINE's call, and the kernel only files it"
# "l'ultimo messaggio suo è 'Va bene, la ringrazio tanto'. Da quando si risponde
# ai ringraziamenti per un task completato?" — twenty-two of those sat in the
# queue's second section, which the operator was expected to read in full. The
# sweep could see that we had answered; it could not see that nothing was left
# to say, and it must not learn to: that is meaning, and meaning is the engine's
# (`emails.needs_reply`). Guards, in order: a settled courtesy leaves the
# headline and keeps printing with the engine's own reason; NO engine answer
# reads exactly as before, never quieter; a verdict cannot settle a conversation
# we never answered; a STALE verdict cannot reach a newer message on the same
# thread; an unanswered conversation still outranks the same contact's
# thank-you; an autoresponder stays `automatic`; a thank-you no longer re-opens
# a contact closed by phone, while a real request still does; nothing dropped.
if "$VENV/bin/python" "$ROOT/tests/test_unanswered_courtesy.py"; then echo "OK"; else echo "FAIL: the closing-courtesy split regressed"; FAIL=1; fi

step "40. every draft carries a verdict, computed from the mailbox"
# A reply sat in the queue while the customer had already written again, and
# /cs-review presented it as ready to send: `cs review` listed both draft stores
# raw, and the triage skill's candidate feed (`cs unanswered`) drops a thread as
# soon as a real message of ours follows the customer's last one — so the thread
# was a candidate nowhere. Guards: a LATER inbound is `overtaken` and an earlier
# one is not; a later send of ours is `superseded`; the engine's own verdict
# lands as `settled` and only on ITS thread; the customer having written since
# outranks both; the two copies of one mirrored draft are ONE row with BOTH
# handles and the EARLIER timestamp; every degradation (mailbox, engine, a draft
# with no date) is a note that leaves the row `ready` — nothing is ever retired
# by a failure to read; and `cs review` carries the verdict into --json and
# prints the two blocks.
if "$VENV/bin/python" "$ROOT/tests/test_draft_state.py"; then echo "OK"; else echo "FAIL: draft verdicts regressed"; FAIL=1; fi

step "41. cs cron status --json + cs catchup (the review's freshness half)"
# The review used to infer the state of the unattended operator from a six-line
# log tail: it read a quiet log as a fault and a bare timestamp as work done
# when the run had skipped. Guards: `absent` / `paused` / `stale` / `ticking`
# are distinguished, the pause outranks staleness and an absent entry outranks
# both, the staleness threshold comes from the SCHEDULE (the same log is fresh
# daily and stale 2-hourly) and the last run says what it did. For `cs catchup`:
# the engine's own two passes in order, the task DIFF reported rather than the
# fact it ran, a failed first pass exits non-zero instead of reading as done,
# the engine's `busy` answer is a clean exit (it is the single-flight guard
# working, not a failure), and `--check` runs NO pass and never offers one on a
# question it could not answer.
if "$VENV/bin/python" "$ROOT/tests/test_catchup_cron.py"; then echo "OK"; else echo "FAIL: cron status / catchup regressed"; FAIL=1; fi

step "42. one shared preamble, both stamping paths, and no Italian in a clone"
# Two properties of what a clone RECEIVES. (1) The desk preamble is one text
# included three times from a partials root that is a SIBLING of the project
# templates — a partial inside would be stamped into every clone as an orphan
# file. Its failure mode is invisible at `cs init`: the update path built its
# Jinja env with NO loader, so the first {% include %} rendered fine for a new
# clone and raised "no loader for this environment specified" on every existing
# one — both paths are exercised, the update one as a REAL `cs update`
# subprocess against a clone whose frozen init_data predates both the include
# and `operator_voice`. Under this venv that subprocess runs the INSTALLED
# package, which is also what proves the templates/partials package-data glob.
# (2) The kernel default is a US-English product: the rendered .claude/ tree
# from the DEFAULT manifest carries no Italian, `cs review`'s digest is English
# kernel code, and the voice a clone declares in its own manifest.toml reaches
# the stamp without re-running `cs init`.
if "$VENV/bin/python" "$ROOT/tests/test_stamped_surfaces.py"; then echo "OK"; else echo "FAIL: stamped surfaces regressed"; FAIL=1; fi

echo
if [ "$FAIL" -ne 0 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: all gates green"
