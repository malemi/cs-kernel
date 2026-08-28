"""Template render gate: every .j2 renders under cs init's own jinja env.

Three configurations, because they break differently:

* **single-account** — the minimal clone. `... | reject(...) | first` on the
  account registry crashed here under StrictUndefined (found 2026-07-30 in
  FOUR templates): the smallest possible clone could not render its own
  CLAUDE.md at `cs init` time.
* **multi-account** — the founder-sweep shape the existing clones use.
* **email-account** — an account name that IS an email
  (`mario.alemi@mrcall.ai`), the shape the kernel's own docs recommend
  ("prefer the mailbox address, never a bare first name") and both live
  clones actually use. Found live 2026-08-21: `manifest.toml.j2` rendered
  that name as a BARE TOML key (`{{ name }} = "{{ uid }}"`) — `@` is
  illegal in a bare key, so the render was invalid TOML the instant an
  operator's own `cs update` re-rendered it. Neither SINGLE nor MULTI
  above happened to use an `@`-bearing name, so this gate ran green while
  the defect shipped. Fixed via a `toml_quote` filter (`cs/project_init.py`)
  applied to every account key AND value; this config plus the TOML-parse
  assertion below is what would have caught it.

Every rendered output is also swept for company literals: the grep gate reads
the template SOURCE, but a literal can be assembled by the template engine,
and what a clone actually receives is the render.
"""
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cs.project_init import build_jinja_env  # noqa: E402

TPL = Path(__file__).resolve().parent.parent / "cs" / "templates" / "project"

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
    imap_host="imap.example.com", imap_port="993",
    timezone="Europe/Rome",
    cron_comment="acme-cs", cron_schedule="0 8 * * *",
    firebase_sa_path="~/.acme-cs/firebase-sa.json",
    founder_sweep_enabled=False, founder_sweep_account="",
    excluded_campaign="", repo_docs_shape="generic",
    repo_git_remote="git@example.com:acme/acme-cs.git", repo_kernel_version="v0.4.0",
    name="Acme", dest_dir="acme-cs",
    operator_voice="American English, professional and direct",
    # The normal case: a clone with no executables of its own. The populated
    # case is gate 17's, which compares the expanded deny list token by token.
    local_scripts_cron_denied=[],
)
SINGLE = {**BASE, "accounts": {"support": "UID123"}, "accounts_default": "support"}
MULTI = {**BASE, "accounts": {"support": "UID123", "founder": "UID999"},
         "accounts_default": "support"}
EMAIL_ACCOUNT = {
    **BASE,
    "accounts": {"support": "UID123", "jane.doe@acme.example": "UID999"},
    "accounts_default": "support",
}

# cs init's OWN environment, partials root included: a template that
# `{% include %}`s a shared fragment must render here exactly as it renders
# during a real stamp, or this gate proves nothing about the stamp.
env = build_jinja_env(TPL)

BAD = ("mrcall.ai", "mario", "eva fani", "cafe124", "centralix", "/home/mal")
fails = 0
templates = sorted(p.relative_to(TPL).as_posix() for p in TPL.rglob("*.j2"))
expected_skills = {
    "cs-account", "cs-campaign", "cs-campaign-tick", "cs-cron", "cs-customer",
    "cs-find-document", "cs-help", "cs-operator", "cs-review", "cs-triage-mail",
}
rendered_skill_names: dict[str, set[str]] = {}
for label, ctx in (("single-account", SINGLE), ("multi-account", MULTI),
                    ("email-account", EMAIL_ACCOUNT)):
    rendered_skill_names[label] = set()
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
        if name == "manifest.toml.j2":
            try:
                tomllib.loads(out)
            except tomllib.TOMLDecodeError as e:
                print(f"  FAIL invalid TOML [{label}] {name}: {e}\n--- rendered ---\n{out}")
                fails += 1
        if name.startswith(".claude/skills/") and name.endswith("/SKILL.md.j2"):
            lines = out.splitlines()
            if not lines or lines[0] != "---" or "---" not in lines[1:]:
                print(f"  FAIL skill frontmatter [{label}] {name}")
                fails += 1
                continue
            end = lines[1:].index("---") + 1
            fields = dict(
                line.split(":", 1) for line in lines[1:end]
                if ":" in line and not line.startswith(" ")
            )
            skill_name = fields.get("name", "").strip()
            description = fields.get("description", "").strip()
            if not skill_name or not description:
                print(f"  FAIL skill name/description [{label}] {name}")
                fails += 1
            if skill_name in rendered_skill_names[label]:
                print(f"  FAIL duplicate skill name [{label}] {skill_name}")
                fails += 1
            rendered_skill_names[label].add(skill_name)

for label, names in rendered_skill_names.items():
    if names != expected_skills:
        print(f"  FAIL skill set [{label}]: {sorted(names)}")
        fails += 1
if (TPL / ".claude" / "commands").exists():
    print("  FAIL fresh template tree still contains .claude/commands")
    fails += 1
print(f"{len(templates)} templates x 3 configs: "
      + ("ALL RENDER CLEAN" if not fails else f"{fails} FAILURES"))
sys.exit(1 if fails else 0)
