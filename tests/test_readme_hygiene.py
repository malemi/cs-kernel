#!/usr/bin/env python3
"""The rendered clone README must not carry kernel-authoring leftovers.

An adversarial UX review (2026-08) found three families of defect in
`cs/templates/project/README.md.j2` (and the sibling `docs/ARCHITECTURE.md.j2`)
that a normal template-render check does not catch, because each one
renders to syntactically valid, plausible-looking prose:

  (i)   a hardcoded `desktop.example.com` engine host instead of the real
        `{{ engine_ws_url }}` — every company's README told them to connect
        to a host that is not theirs;
  (ii)  an unguarded Jinja variable that is EMPTY for the common case
        (`excluded_campaign=""`, `crm_adapter='none'`, `producer_adapter='none'`)
        renders as visible garbage — e.g. the literal text "The `` campaign
        is carved out to a dedicated process." — instead of omitting the
        bullet;
  (iii) Italian strings ("Bozze", "invia la bozza per X") shipped inside an
        artifact whose charter is English-only.

This test renders README.md.j2 through `cs init`'s own jinja env, once with
the common/default shape (excluded_campaign="", crm_adapter="none",
producer_adapter="none") and once with all three populated, and asserts
none of the three defect families is present in either render.

Scope note: this Italian check covers ONLY the rendered clone README and
other operator-facing prose meant to be English by charter — it must never
be widened to `cs/templates/project/.claude/`'s skill/command reports,
where "Italian, founders' register" is a deliberate, exempted product
choice (the daily digest's audience is an Italian-reading human operator,
per the charter's non-English-end-user exemption), not a defect.
"""
from __future__ import annotations

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
    cs_triage_mode="draft", dedup_days="30", reminder_max="2",
    system_senders="", send_guard_min_chars=40, send_guard_banned_phrases="",
    sms_enabled=False, sms_hour="18", sms_proxy_base="",
    smtp_host="smtp.example.com", smtp_port="587",
    imap_host="imap.example.com", imap_port="993",
    timezone="Europe/Rome",
    cron_comment="acme-cs", cron_schedule="0 8 * * *",
    firebase_sa_path="~/.acme-cs/firebase-sa.json",
    founder_sweep_enabled=False, founder_sweep_account="",
    excluded_campaign="", repo_docs_shape="as-built",
    repo_git_remote="git@example.com:acme/acme-cs.git", repo_kernel_version="v0.6.1",
    name="Acme", dest_dir="acme-cs",
)
DEFAULTS_SHAPE = {**BASE, "accounts": {"support": "UID123"}, "accounts_default": "support"}
POPULATED_SHAPE = {
    **BASE,
    "excluded_campaign": "spring-migration",
    "crm_adapter": "shopify",
    "producer_adapter": "mrcall-tracking",
    "accounts": {"support": "UID123"},
    "accounts_default": "support",
}

# Italian strings the adversarial review found verbatim in the pre-fix
# template — must never reach a rendered clone.
ITALIAN_LEFTOVERS = ("Bozze", "invia la bozza")

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TPL), trim_blocks=True, lstrip_blocks=True,
    undefined=jinja2.StrictUndefined,
)


def _render(shape: dict) -> str:
    return env.get_template("README.md.j2").render(**shape)


def _test_no_hardcoded_engine_host() -> None:
    for label, shape in (("defaults", DEFAULTS_SHAPE), ("populated", POPULATED_SHAPE)):
        out = _render(shape)
        assert "example.com" not in out or "engines.example.com" in out, (
            f"[{label}] unexpected example.com literal leaked into the README:\n{out}"
        )
        assert "desktop.example.com" not in out, (
            f"[{label}] README must not hardcode desktop.example.com — it must use "
            f"{{{{ engine_ws_url }}}}:\n{out}"
        )
        assert shape["engine_ws_url"] in out, (
            f"[{label}] the configured engine_ws_url must actually appear in the README"
        )


def _test_no_empty_variable_artifacts() -> None:
    # The common case: excluded_campaign / crm_adapter / producer_adapter all
    # at their "nothing configured" default must not render a bullet with an
    # empty backtick pair or a bullet naming the 'none' adapter as if it were
    # real CRM/producer wiring.
    out = _render(DEFAULTS_SHAPE)
    assert "The `` campaign" not in out, (
        f"empty-variable artifact leaked into the README:\n{out}"
    )
    assert "dossier query none" not in out, (
        f"the CRM bullet must be omitted when crm_adapter='none', not render the "
        f"literal adapter name as if it were configured:\n{out}"
    )
    assert "reads the `none` producer" not in out, (
        f"the producer bullet must be omitted when producer_adapter='none':\n{out}"
    )

    # The populated case must render the real bullets, proving the guard is a
    # visibility toggle and not a silent delete of the feature.
    out_pop = _render(POPULATED_SHAPE)
    assert "spring-migration" in out_pop, (
        f"the excluded-campaign bullet must render when excluded_campaign is set:\n{out_pop}"
    )
    assert "shopify" in out_pop, (
        f"the CRM bullet must render when crm_adapter is set:\n{out_pop}"
    )
    assert "mrcall-tracking" in out_pop, (
        f"the producer bullet must render when producer_adapter is set:\n{out_pop}"
    )


def _test_no_italian_leftovers() -> None:
    for label, shape in (("defaults", DEFAULTS_SHAPE), ("populated", POPULATED_SHAPE)):
        out = _render(shape)
        for leftover in ITALIAN_LEFTOVERS:
            assert leftover not in out, (
                f"[{label}] Italian string {leftover!r} leaked into the rendered "
                f"README (English-only artifact):\n{out}"
            )
        assert "**Drafts**" in out, (
            f"[{label}] the Gmail-Drafts pointer must be in English:\n{out}"
        )
        assert 'cs chat "send the draft' in out, (
            f"[{label}] the send-draft example must be in English:\n{out}"
        )


def main() -> int:
    _test_no_hardcoded_engine_host()
    _test_no_empty_variable_artifacts()
    _test_no_italian_leftovers()
    print("test_readme_hygiene: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
