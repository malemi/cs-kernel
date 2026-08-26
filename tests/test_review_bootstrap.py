#!/usr/bin/env python3
"""`/cs-review` — the ONE command an operator types when he sits down.

Why this gate exists. The command was measured against a real morning
(2026-08-26) and answered three of the eight questions a returning operator
actually has. Four things it got wrong, each of which is asserted here:

  1. **The kill-switch was surfaced BY ACCIDENT** — the six-line cron log tail
     happened to be all `paused … skip`, so the greeting inferred a warning
     from it. No step read the switch, and the inference carried a derived
     claim ("all the ticks of the last 12 hours") that was wrong by 4x because
     six lines of a 2-hourly log are twelve hours by construction, whatever the
     real gap. Now `cs config` is a step, and the greeting is forbidden from
     deriving a span from a fixed-length tail.
  2. **The pause was framed as a fault, and the first suggestion was to clear
     it** — without mentioning that `cs_triage_mode` is `send`, i.e. it
     recommended resuming real sending without saying it was a sending mode.
     The pause is the operator's standing decision: ONE neutral field of state,
     never an alarm, never a suggestion.
  3. **Everything collapsed into counts.** Eight Gmail drafts became `8 bozze`,
     so a reply waiting for a named customer was unreachable without opening
     something else; the out-of-band records the verb prints were dropped
     entirely, which is how a contact deliberately taken OUT of the queue gets
     re-raised from memory.
  4. **Thirty-one identical `[engaged]` rows** for one campaign — 31 of the
     block's 37 lines — earned nothing and crowded out the rest.

Asserted here:

  A. `review.gather` COUNTS plain campaign outcomes and LISTS escalations; an
     excluded campaign is labelled, never hidden (its escalations are still
     the operator's).
  B. `unanswered.crm_annotate` labels a row from the adapter's own
     `render_hints`, marks a row with no record, and on a DEGRADED backend
     returns one note and labels nothing — a half-filled column reads as
     "these are not customers", which is the one wrong answer.
  C. `cs unanswered --crm` groups customers separately; WITHOUT the flag the
     output is exactly the table it has always been (the triage skill parses
     it).
  D. The rendered command file carries the steps that answer the eight
     questions — `cs config`, `cs --version`, `git log`, the 45-day CRM sweep,
     the owner-actions digest — and its greeting shape obeys the four pause
     rules literally.
  E. The project settings allow the read-only verbs the command runs, so the
     one command the operator types does not stop on a permission prompt.

Hermetic: no engine, no mailbox, no network.
"""
from __future__ import annotations

import io
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

import jinja2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cs import cli, review, unanswered  # noqa: E402
from cs.crm import CrmResult, CrmRow  # noqa: E402
from cs.project_init import toml_quote  # noqa: E402

TPL = Path(__file__).resolve().parent.parent / "cs" / "templates" / "project"

fails = 0


def check(cond, msg: str) -> None:
    global fails
    if not cond:
        print(f"  FAIL: {msg}")
        fails += 1


# ------------------------------------------------------- A. campaign block

def _campaigns() -> None:
    """31 `[engaged]` rows become one number; an ESCALATION keeps its address
    and its reason, because it exists to fetch a human."""
    engaged = [
        {"email": f"c{i}@example.test", "state": "replied",
         "dossier": {"outcome": "engaged"}}
        for i in range(31)
    ]
    engaged.append({"email": "help@example.test", "state": "sent",
                    "dossier": {"escalated": True,
                                "escalate_reason": "chiede il rimborso"}})
    engaged.append({"email": "no@example.test", "state": "sent",
                    "dossier": {"outcome": "declined"}})

    settings = types.SimpleNamespace(
        excluded_campaign_set={"owned-elsewhere"},
        db_path="/nonexistent/cs.db",
        timezone="Europe/Rome",
        log_path=Path("/nonexistent/cs_operator.log"),
    )

    def _list_campaigns(_s):
        return [{"id": "1", "name": "owned-elsewhere",
                 "contacts_by_state": {"sent": 33}},
                {"id": "2", "name": "ours", "contacts_by_state": {"sent": 1}}]

    def _call_sync(_s, method, params=None, **kw):
        if method == "campaign.contacts":
            return engaged if params.get("campaign_id") == "1" else []
        raise RuntimeError("no engine in this test")

    orig_list, orig_rpc = review.campaign.list_campaigns, review.rpc.call_sync
    review.campaign.list_campaigns = _list_campaigns
    review.rpc.call_sync = _call_sync
    try:
        d = review.gather(settings)
    finally:
        review.campaign.list_campaigns = orig_list
        review.rpc.call_sync = orig_rpc

    camp = {c["campaign"]: c for c in d["campaigns"]}
    check(set(camp) == {"owned-elsewhere", "ours"},
          f"both campaigns must be present, got {sorted(camp)}")
    first = camp["owned-elsewhere"]
    check(first["outcomes"] == {"engaged": 31, "declined": 1},
          f"plain outcomes must be counted, got {first['outcomes']}")
    check([f["email"] for f in first["flagged"]] == ["help@example.test"],
          f"only the escalation is listed, got {first['flagged']}")
    check(first["excluded"] is True,
          "a campaign named in excluded_campaign_set must be labelled excluded")
    check(camp["ours"]["excluded"] is False,
          "a campaign nobody else owns is not excluded")

    out = review.render(d)
    block = out.split("Campagne:", 1)[1]
    check(block.count("[engaged]") == 0,
          "no per-contact row for a plain outcome — that is the 31-line regression")
    check("engaged 31" in block, f"the count must be printed:\n{block}")
    check("help@example.test" in block and "chiede il rimborso" in block,
          f"the escalation keeps address + reason:\n{block}")
    check("esclusa" in block,
          f"the excluded campaign must say so, not disappear:\n{block}")
    # The whole block, for a pack mid-run, is now a handful of lines.
    check(len(block.strip().splitlines()) <= 6,
          f"campaign block must stay short, got:\n{block}")


# ---------------------------------------------------------- B. CRM column

def _crm_annotate() -> None:
    def _lookup(_s, email):
        if email == "customer@example.test":
            return CrmResult(
                source="fake", ok=True, note=None,
                rows=[CrmRow(id="1", label="Acme", email=email,
                             facts={"status": "ACTIVE", "template": "essential"})],
                render_hints=["status", "template"],
            )
        if email == "two@example.test":
            return CrmResult(
                source="fake", ok=True, note=None,
                rows=[CrmRow(id="1", label="A", email=email, facts={"status": "FREE"}),
                      CrmRow(id="2", label="B", email=email, facts={"status": "ACTIVE"})],
                render_hints=["status"],
            )
        return CrmResult(source="fake", ok=True, note=None, rows=[], render_hints=[])

    rows = [{"email": "customer@example.test"}, {"email": "two@example.test"},
            {"email": "stranger@example.test"}]
    note = unanswered.crm_annotate(None, rows, lookup=_lookup)
    check(note is None, f"a healthy backend yields no note, got {note!r}")
    check(rows[0]["crm"] == "ACTIVE/essential" and rows[0]["crm_known"] is True,
          f"label comes from render_hints, got {rows[0]}")
    check(rows[1]["crm"] == "FREE (+1)" and rows[1]["crm_known"] is True,
          f"a second record is counted, not dropped, got {rows[1]}")
    check(rows[2]["crm"] == "" and rows[2]["crm_known"] is False,
          f"no record → no label, got {rows[2]}")

    # Degraded: ONE note, and nothing is labelled. A column that is filled for
    # some rows and empty for others would say "these are not customers".
    def _degraded(_s, _email):
        return CrmResult(source="stub", ok=False, note="set CRM_TOKEN",
                         rows=[], render_hints=[])

    rows = [{"email": "a@example.test"}, {"email": "b@example.test"}]
    note = unanswered.crm_annotate(None, rows, lookup=_degraded)
    check(note == "set CRM_TOKEN", f"the degradation note is returned once, got {note!r}")
    check(all(r["crm_known"] is False and r["crm"] == "" for r in rows),
          f"a degraded backend labels nothing, got {rows}")

    # The port promises never to raise; if it ever does, the sweep still prints.
    def _boom(_s, _email):
        raise RuntimeError("backend on fire")

    rows = [{"email": "a@example.test"}]
    note = unanswered.crm_annotate(None, rows, lookup=_boom)
    check("backend on fire" in (note or ""), f"a raising lookup is caught, got {note!r}")
    check(rows[0]["crm_known"] is False, "a raising lookup leaves the row unlabelled")


# ------------------------------------------------------- C. the CLI surface

def _cli_grouping() -> None:
    settings = types.SimpleNamespace(prog_name="cs", email_address="s@example.test")
    sweep_out = {
        "open": [
            {"email": "cust@example.test", "days_waiting": 25, "subject": "Guasto",
             "last_inbound_date": None},
            {"email": "robot@example.test", "days_waiting": 3, "subject": "Newsletter",
             "last_inbound_date": None},
        ],
        "handled": [],
        "escalated": [],
    }

    def _sweep(_s, days):
        import copy
        return copy.deepcopy(sweep_out)

    def _annotate(_s, rows, lookup=None):
        for r in rows:
            known = r["email"].startswith("cust")
            r["crm"], r["crm_known"] = ("ACTIVE/essential" if known else ""), known
        return None

    orig_load, orig_sweep, orig_ann = (
        cli.config.load, unanswered.sweep, unanswered.crm_annotate)
    cli.config.load = lambda: settings
    unanswered.sweep = _sweep
    unanswered.crm_annotate = _annotate
    try:
        plain = io.StringIO()
        with redirect_stdout(plain):
            cli.cmd_unanswered(types.SimpleNamespace(days=45, json=False, crm=False))
        grouped = io.StringIO()
        with redirect_stdout(grouped):
            cli.cmd_unanswered(types.SimpleNamespace(days=45, json=False, crm=True))
    finally:
        cli.config.load = orig_load
        unanswered.sweep = orig_sweep
        unanswered.crm_annotate = orig_ann

    p, g = plain.getvalue(), grouped.getvalue()
    check(p.splitlines()[0].startswith("EMAIL"),
          f"without --crm the table is unchanged, got:\n{p}")
    check("clienti" not in p and "CRM" not in p,
          f"without --crm nothing about the CRM appears:\n{p}")
    check("clienti (in CRM) — 1:" in g, f"customers get their own group:\n{g}")
    check("non in CRM — 1:" in g, f"the rest get theirs:\n{g}")
    check(g.index("cust@example.test") < g.index("robot@example.test"),
          f"customers come first:\n{g}")
    check("ACTIVE/essential" in g, f"the CRM facts are shown:\n{g}")
    check("total: 2 unanswered (oldest first)" in g and
          "total: 2 unanswered (oldest first)" in p,
          "the total is printed either way")


# ------------------------------------------------ D. the rendered command

BASE = dict(
    company_name="Acme Corp", company_display_name="Acme", company_from_name="Acme Support",
    company_slug="acme", company_prog_name="acme-cs",
    email_address="support@acme.example", engine_owner_uid="UID123",
    engine_ws_url="wss://engines.example.com",
    platform_env_path="", producer_adapter="none", producer_mrcall_tracking=False,
    crm_adapter="none", crm_shopify=False, drive_scope="",
    cs_triage_mode="draft", dedup_days="30", reminder_max="2",
    system_senders="", send_guard_min_chars=40, send_guard_banned_phrases="",
    sms_enabled=False, sms_hour="18", sms_proxy_base="",
    smtp_host="smtp.example.com", smtp_port="587",
    imap_host="imap.example.com", imap_port="993", timezone="Europe/Rome",
    cron_comment="acme-cs", cron_schedule="0 8 * * *",
    firebase_sa_path="~/.acme-cs/firebase-sa.json",
    founder_sweep_enabled=False, founder_sweep_account="",
    excluded_campaign="", repo_docs_shape="generic",
    repo_git_remote="git@example.com:acme/acme-cs.git", repo_kernel_version="v0.4.0",
    name="Acme", dest_dir="acme-cs",
    accounts={"support": "UID123"}, accounts_default="support",
)

# Words that turn a standing decision into an accusation. The operator's own
# ruling: "SONO IO CHE DECIDO CHE NON DEVE ANDARE, FINE. BASTA DIRMELO UNA
# VOLTA." A greeting that scolds him for his own switch is a defect.
ALARM_WORDS = ("⚠", "attenzione", "problema", "bloccato", "warning", "alert", "!!")


def _rendered_command() -> None:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TPL), trim_blocks=True,
                             lstrip_blocks=True, undefined=jinja2.StrictUndefined)
    env.filters["toml_quote"] = toml_quote
    for label, ctx in (("reply-only", BASE),
                       ("with-producer", {**BASE, "producer_adapter": "acme-leads",
                                          "crm_adapter": "shopify"})):
        out = env.get_template(".claude/commands/cs-review.md.j2").render(**ctx)

        # The steps that answer the questions the command used to leave open.
        for needle, why in (
            ("cs config", "the settings in force must be READ, never inferred"),
            ("cs --version", "the kernel pin comes from the installed package"),
            ("git log", "what changed since he last sat down"),
            ("cs unanswered --days 45 --crm", "the support queue, customers apart"),
            ("docs/owner-actions.md", "what is blocked on him"),
            ("cs review", "what the headless operator prepared"),
        ):
            check(needle in out, f"[{label}] the command must run/read `{needle}` — {why}")

        # The greeting shape: the fenced block the model fills in.
        shape = out.split("### The shape", 1)[1].split("```", 2)[1]

        # Rule 2, mechanically. `pausa` is one neutral field of state.
        check(shape.count("pausa") == 1,
              f"[{label}] the pause appears exactly ONCE in the greeting shape, "
              f"got {shape.count('pausa')}:\n{shape}")
        check("in pausa (decisione tua)" in shape,
              f"[{label}] and it is framed as his decision:\n{shape}")
        check("CS_PAUSE" not in shape,
              f"[{label}] the greeting names a state, not a file:\n{shape}")
        for w in ALARM_WORDS:
            check(w not in shape.lower(),
                  f"[{label}] the greeting shape must not raise an alarm about it: {w!r}")
        # Rule 2 again: nothing anywhere in the file may hand him a way to
        # clear the switch — a review is not the place that decision is made.
        check("rm ~/." not in out and "rm -f ~/." not in out,
              f"[{label}] /cs-review must never offer to remove the kill-switch file")
        closing = shape.split("Da dove partiamo?", 1)[1]
        for w in ("pausa", "CS_PAUSE", "cron", "tick", "ripart"):
            check(w not in closing.lower(),
                  f"[{label}] the closing options must not mention {w!r}:\n{closing}")

        # Rule 4: nothing that would make him open something else.
        check("[uid <uid>]" in shape,
              f"[{label}] every draft is a row with its uid, not a count:\n{shape}")
        check("Fuori coda" in shape,
              f"[{label}] out-of-band records get their own line:\n{shape}")
        check("Coda support" in shape,
              f"[{label}] the support queue has a slot:\n{shape}")
        check("Repo:" in shape and "In attesa di te:" in shape,
              f"[{label}] repo state + what is blocked on him have slots:\n{shape}")
        check("modo:" in shape,
              f"[{label}] cs_triage_mode is stated next to the pause — resuming a "
              f"send-mode operator is not the same decision as resuming a draft one")


# ----------------------------------------------- E. it runs without prompts

def _permissions() -> None:
    import json

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TPL), trim_blocks=True,
                             lstrip_blocks=True, undefined=jinja2.StrictUndefined)
    env.filters["toml_quote"] = toml_quote
    settings = json.loads(env.get_template(".claude/settings.json.j2").render(**BASE))
    allow = settings["permissions"]["allow"]
    for entry in ("Bash(.venv/bin/python -m cs review:*)",
                  "Bash(.venv/bin/python -m cs unanswered:*)",
                  "Bash(.venv/bin/python -m cs config:*)",
                  "Bash(.venv/bin/python -m cs --version:*)",
                  "Bash(git log:*)", "Bash(git status:*)"):
        check(entry in allow,
              f"/cs-review runs {entry} — the one command must not stop on a prompt")
    # Still read-only: the git entries are log/status, never a write verb.
    for entry in allow:
        if entry.startswith("Bash(git "):
            check(entry in ("Bash(git log:*)", "Bash(git status:*)"),
                  f"only read-only git is allowed, found {entry}")


_campaigns()
_crm_annotate()
_cli_grouping()
_rendered_command()
_permissions()

if fails:
    print(f"test_review_bootstrap: {fails} assertion(s) FAILED")
    sys.exit(1)
print("test_review_bootstrap: all assertions passed")
