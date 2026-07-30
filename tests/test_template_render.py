"""Template render gate: every .j2 renders under cs init's own jinja env.

Two configurations, because they break differently:

* **single-account** — the minimal clone. `... | reject(...) | first` on the
  account registry crashed here under StrictUndefined (found 2026-07-30 in
  FOUR templates): the smallest possible clone could not render its own
  CLAUDE.md at `cs init` time.
* **multi-account** — the founder-sweep shape the existing clones use.

Every rendered output is also swept for company literals: the grep gate reads
the template SOURCE, but a literal can be assembled by the template engine,
and what a clone actually receives is the render.
"""
import sys
from pathlib import Path

import jinja2

TPL = Path(__file__).resolve().parent.parent / "cs" / "templates" / "project"

BASE = dict(
    company_name="Acme Corp", company_display_name="Acme", company_from_name="Acme Support",
    company_slug="acme", company_prog_name="acme-cs",
    email_address="support@acme.example", engine_owner_uid="UID123",
    engine_ws_url="wss://engines.example.com",
    platform_env_path="", producer_adapter="none", producer_mrcall_tracking=False,
    crm_adapter="none", crm_shopify=False, drive_scope="",
    rate_cap="25", cs_triage_mode="draft", dedup_days="30", reminder_max="2",
    sms_enabled=False, sms_hour="18", sms_proxy_base="",
    smtp_host="smtp.example.com", smtp_port="587",
    imap_host="imap.example.com", imap_port="993",
    timezone="Europe/Rome", autonomous=False, dry_run=True,
    cron_comment="acme-cs", cron_schedule="0 8 * * *",
    firebase_sa_path="~/.acme-cs/firebase-sa.json",
    founder_sweep_enabled=False, founder_sweep_account="",
    excluded_campaign="", repo_docs_shape="generic",
    repo_git_remote="git@example.com:acme/acme-cs.git", repo_kernel_version="v0.4.0",
    posture_note="", name="Acme", dest_dir="acme-cs",
)
SINGLE = {**BASE, "accounts": {"support": "UID123"}, "accounts_default": "support"}
MULTI = {**BASE, "accounts": {"support": "UID123", "founder": "UID999"},
         "accounts_default": "support"}

env = jinja2.Environment(loader=jinja2.FileSystemLoader(TPL), trim_blocks=True,
                         lstrip_blocks=True, undefined=jinja2.StrictUndefined)

BAD = ("mrcall.ai", "mario", "eva fani", "cafe124", "centralix", "/home/mal")
fails = 0
templates = sorted(p.relative_to(TPL).as_posix() for p in TPL.rglob("*.j2"))
for label, ctx in (("single-account", SINGLE), ("multi-account", MULTI)):
    for name in templates:
        try:
            out = env.get_template(name).render(**ctx)
        except Exception as e:
            print(f"  FAIL render [{label}] {name}: {type(e).__name__}: {e}")
            fails += 1
            continue
        leaked = [b for b in BAD if b in out.lower()]
        if leaked:
            print(f"  FAIL literal [{label}] {name}: {leaked}")
            fails += 1
print(f"{len(templates)} templates x 2 configs: "
      + ("ALL RENDER CLEAN" if not fails else f"{fails} FAILURES"))
sys.exit(1 if fails else 0)
