"""Captured notices retain actionable evidence, identity and severity."""
from html.parser import HTMLParser
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from cs import operator_notices, operator_recovery
from cs.config import Settings

class MessageHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = ""
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.text += "\n"
        if tag == "a":
            self.links.append(dict(attrs)["href"])

    def handle_data(self, data):
        self.text += data


with tempfile.TemporaryDirectory() as directory:
    settings = Settings(slug="sample", email_address="recipient@example.test", state_dir=Path(directory))
    context = {"workspace": "Sample", "manifest_path": "/srv/operator/manifest.toml",
               "auth_command": "/opt/claude auth status --json", "config_command": "cs config show",
               "doctor_command": "cs doctor", "status_command": "cs cron status",
               "log_command": "tail -n 100 -- /srv/operator/run.log", "log_path": "/srv/operator/run.log",
               "fallback_budget_usd": 2, "fallback_model": "claude-example"}
    base = {"provider": "OpenRouter", "account_email": "payer@example.test",
            "key_fingerprint": "sk-or-v1-ab…1234", "organization_id": "org-payer",
            "context": context, "http_status": 402, "exit_code": 1, "session_id": "session-123"}
    items = [{"status": "stopped", "reason": "unknown_failure", "diagnostic": {**base, "cause": cause}}
             for cause in operator_notices.CAUSES]
    legacy = [{"status": "stopped", "reason": reason} for reason in operator_notices.LEGACY_CAUSES]
    items += legacy
    items += [{"status": "primary", "model_only": True, "model": "model-a"},
              {"status": "primary", "model": "model-a"},
              {"status": "fallback", "reason": "payment_required", "diagnostic": {
                  **base, "cause": "unknown_failure", "primary": {**base, "cause": "credit_refusal",
                  "provider": "Anthropic API", "account_email": "primary-payer@example.test"}}}]
    captured = []

    def capture(_settings, item):
        subject, plain, html = operator_notices.render(_settings, item)
        parts = {"plain": plain, "html": html}
        assert "URGENT" not in subject
        body = parts["plain"]
        parsed = MessageHTML()
        parsed.feed(parts["html"])
        assert parsed.text == body
        assert all(url in operator_notices.OFFICIAL_REPAIR_URLS for url in parsed.links)
        for url in operator_notices.OFFICIAL_REPAIR_URLS:
            if url in body:
                assert url in parsed.links
        assert all(part in body for part in ("Symptom:", "Cause:", "Affected provider:", "Action to repair", "After repair"))
        assert "administrator" not in body
        assert "not evidence of the provider billing account" in body
        captured.append((subject, body))

    state = {"current": "primary|model-a||", "seen_primary": True, "pending": items}
    operator_recovery._write_state(settings, state)
    loaded = operator_recovery._read_state(settings)
    with patch("cs.operational_inbox.record_notice", capture):
        assert operator_recovery._notice(settings, loaded, "primary", "model-a")
    assert len(captured) == len(items)
    assert json.loads(operator_recovery._state_path(settings).read_text())["pending"] == []
    for item, (subject, body) in zip(items, captured):
        if item["status"] == "stopped":
            assert subject.startswith("ACTION REQUIRED:")
            assert "Some actions may already have happened" in body
        else:
            assert subject.startswith(("INFO:", "RESOLVED:"))
        if "diagnostic" in item:
            assert "Provider account email: payer@example.test" in body or "primary-payer@example.test" in body
            assert "cs cron status" in body

    def render(cause, provider="OpenRouter", **extra):
        return operator_notices.render(settings, {"status": "stopped", "reason": "fallback_failed",
            "diagnostic": {**base, "cause": cause, "provider": provider, **extra}})[1]

    credit = render("credit_refusal")
    assert "https://openrouter.ai/settings/credits" in credit
    assert "Provider workspace ID: not captured" not in credit
    assert "does not by itself prove" in credit
    cap = render("key_limit", key_limit_remaining=0)
    assert "https://openrouter.ai/settings/keys" in cap
    assert "Adding account credit alone does not raise" in cap
    assert "https://openrouter.ai/settings/credits" not in cap
    api = render("credit_refusal", "Anthropic API")
    assert "https://platform.claude.com/settings/billing" in api
    assert "openrouter.ai" not in api
    unknown = render("credit_refusal", "Unknown")
    assert "definitive repair is not yet known" in unknown
    assert "/opt/claude auth status --json" in unknown and "session-123" in unknown
    assert "settings/credits" not in unknown and "settings/billing" not in unknown
    assert "/opt/claude auth login" in render("auth_failed", "Claude subscription")
    forbidden = render("auth_failed", "Claude subscription", http_status=403)
    assert "logging in again may not fix it" in forbidden and "/opt/claude auth login" not in forbidden
    api_key = render("auth_failed", "Anthropic API", credential_source="ANTHROPIC_API_KEY")
    assert "Replace ANTHROPIC_API_KEY in the environment loaded by the scheduled launcher" in api_key
    absent = render("credit_refusal", account_email=None, key_fingerprint=None, organization_id=None)
    assert "affected provider account could not be identified" in absent
    assert "/opt/claude auth status --json" in absent
    assert "https://claude.ai/settings/usage" in render("quota", "Claude subscription")
    budget = render("budget_exhausted")
    assert "[knobs].cron_fallback_budget_usd" in budget and "/srv/operator/manifest.toml" in budget
    configured = render("fallback_unconfigured")
    assert "[knobs].cron_fallback_model" in configured and "captured" in configured.lower()
    no_work = render("auth_failed", no_work_proven=True)
    assert "confirmed that this attempt did no work" in no_work
    assert "Some actions may already" not in no_work
    secret = render("auth_failed", key_fingerprint="sk-or-raw-credential-that-must-not-leak")
    assert "sk-or-raw" not in secret
    fallback_body = captured[-1][1]
    assert "current work is not blocked" in fallback_body
    assert "Working backup provider: OpenRouter" in fallback_body
    assert "Provider account email: primary-payer@example.test" in fallback_body
    subject, _, _ = operator_notices.render(settings, {
        "status": "stopped", "diagnostic": {**base, "cause": "key_limit"}})
    assert subject == "ACTION REQUIRED: assistant stopped — OpenRouter key spending limit reached"
    _, stopped_both, _ = operator_notices.render(settings, {
        "status": "stopped", "diagnostic": {**base, "cause": "auth_failed", "primary": {
            **base, "cause": "quota", "provider": "Claude subscription"}}})
    assert "fixing the main service alone can restore" in stopped_both
    legacy_identity = {"key": "sk-or-v1-ab…1234", "workspace": "unavailable"}
    _, legacy_failed, _ = operator_notices.render(settings, {
        "status": "stopped", "reason": "fallback_failed", "identity": legacy_identity})
    assert "Affected provider: OpenRouter" in legacy_failed
    _, legacy_success, _ = operator_notices.render(settings, {
        "status": "fallback", "reason": "weekly_limit", "identity": legacy_identity})
    primary_part, backup_part = legacy_success.split("Working backup provider:")
    assert "Affected provider: Claude subscription" in primary_part and "sk-or-v1" not in primary_part
    assert "OpenRouter" in backup_part and "sk-or-v1" in backup_part
    assert "workspace ID: unavailable" not in backup_part
    settings.company_name = '<script>&"'
    _, plain, rich = operator_notices.render(settings, legacy[0])
    assert '<script>' in plain and '<script>' not in rich and '&lt;script&gt;&amp;' in rich

print(f"operator notices: {len(items)} retained-notice renders; provider-specific repair, payer isolation, legacy delivery, severity and HTML OK")
