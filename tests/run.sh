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
CI_HITS="$(grep -rEin --exclude-dir=__pycache__ 'mrcall\.ai|cafe124|124-cs|centralix|/home/mal' cs/ || true)"
# The 'HB' shared-drive literal is UPPERCASE — match it case-SENSITIVELY so the gate
# does not false-positive on the lowercase 'hb' path segment (e.g. ~/hb/…), which is
# a filesystem path, not the drive token.
CS_HITS="$(grep -rEn --exclude-dir=__pycache__ '\bHB\b' cs/ || true)"
if [ -n "$CI_HITS$CS_HITS" ]; then
  [ -n "$CI_HITS" ] && printf '%s\n' "$CI_HITS"
  [ -n "$CS_HITS" ] && printf '%s\n' "$CS_HITS"
  echo "FAIL: company literals found in the kernel package"; FAIL=1
else
  echo "OK"
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

step "4. full --help tree (every verb / sub-verb)"
HELPLOG="$TMP/help_tree.txt"
tree_fail=0
for v in plan whoami rpc thread contacted unanswered tasks business dossier ask draft-reply review drive accounts chat campaign project; do
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

step "11. project memory scaffold (cs project new)"
# The per-project memory shape is only uniform across clones because a generator
# stamps it. Guards: abstract-first + front matter on every stamped file, no
# unrendered Jinja reaching a clone, market-local date, and a REFUSAL on an
# existing folder (clobbering it destroys the only copy of a judgment).
# Runs against the fresh venv, so it also proves the templates are PACKAGED.
if "$VENV/bin/python" "$ROOT/tests/test_project_memory.py"; then echo "OK"; else echo "FAIL: project memory scaffold regressed"; FAIL=1; fi

echo
if [ "$FAIL" -ne 0 ]; then echo "RESULT: FAIL"; exit 1; fi
echo "RESULT: all gates green"
