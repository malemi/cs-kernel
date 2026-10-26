"""Render scheduled-run notices from captured, credential-free diagnostics."""
from __future__ import annotations

import html
import shlex
from typing import Any

from .config import Settings


SUBJECT_CAUSES = {
    "native_task_killed": "native Bash task killed",
    "native_task_stopped": "native Bash task stopped",
    "execution_operation_failed": "draft or contextual action not confirmed",
    "execution_phase_incomplete": "required native execution evidence missing",
    "discovery_inspection_incomplete": "complete discovery inspection missing",
    "mailbox_read_incomplete": "mailbox discovery incomplete",
    "assignment_read_incomplete": "assignment authority incomplete",
    "discovery_evidence_invalid": "discovery evidence missing or invalid",
    "execution_read_failed": "required operator read failed",
    "supervisor_failed": "supervisor execution failed",
    "mail_intake_failed": "email synchronization failed",
    "credit_refusal": "payment or credit refused", "key_limit": "key spending limit reached",
    "auth_failed": "account access rejected", "rate_limit": "request limit reached",
    "quota": "usage allowance exhausted", "provider_unavailable": "service unavailable",
    "request_rejected": "request rejected", "budget_exhausted": "run spending budget reached",
    "max_turns": "run turn limit reached", "timeout": "run time limit reached",
    "invalid_output": "unreadable run result", "output_limit": "run output limit reached",
    "no_result": "run ended without a result", "model_unknown": "backup model not reported",
    "fallback_unconfigured": "backup configuration missing",
    "credential_missing": "backup credential missing", "credential_unavailable": "backup credential unavailable",
    "mode_mismatch": "draft/send permissions mismatch", "unknown_failure": "cause not yet identified",
}

OFFICIAL_REPAIR_URLS = (
    "https://openrouter.ai/settings/credits", "https://openrouter.ai/settings/keys",
    "https://platform.claude.com/settings/billing", "https://claude.ai/settings/usage",
)

LEGACY_CAUSES = {
    "primary_timeout": "timeout", "fallback_timeout": "timeout",
    "weekly_limit": "quota", "usage_limit": "quota",
    "payment_required": "credit_refusal", "fallback_failed": "unknown_failure",
    "fallback_credit_refusal": "credit_refusal", "fallback_rate_limited": "rate_limit",
    "fallback_budget_exhausted": "budget_exhausted", "fallback_model_unknown": "model_unknown",
}

CAUSES = {
    "native_task_killed": "A structured native Bash task was killed before completion. The upstream reason is unknown.",
    "native_task_stopped": "A structured native Bash task stopped before completion. The upstream reason is unknown.",
    "execution_operation_failed": "An attempted native draft or contextual action failed or did not retain its result; completion is not confirmed.",
    "execution_phase_incomplete": "Required native operator phases did not retain their actual results.",
    "discovery_inspection_incomplete": "Complete discovery inspection was not verified before drafting or the end of the run.",
    "mailbox_read_incomplete": "The deterministic discovery could not read the complete mailbox.",
    "assignment_read_incomplete": "Discovery found incomplete technical assignment authority; independently eligible threads may still have been processed.",
    "discovery_evidence_invalid": "The run ended without valid complete discovery evidence for this invocation.",
    "execution_read_failed": "A required native operator read returned an error.",
    "supervisor_failed": "The scheduled supervisor encountered an unexpected execution failure.",
    "mail_intake_failed": "Email synchronization did not return a valid successful email-only result. Neither assistant model was launched.",
    "credit_refusal": "The provider refused payment or credit for a request. This does not by itself prove that the account balance is zero.",
    "key_limit": "The OpenRouter API key has no spending allowance remaining.",
    "auth_failed": "The provider rejected the credentials used for this run.",
    "rate_limit": "The provider temporarily refused requests because a request-rate limit was reached.",
    "quota": "The provider reported that an account usage allowance was exhausted.",
    "provider_unavailable": "The AI provider reported that its service was unavailable.",
    "request_rejected": "The AI provider rejected the request.",
    "budget_exhausted": "The run reached its configured spending budget before completing.",
    "max_turns": "The process reached its maximum number of conversation turns before completing.",
    "timeout": "The process exceeded the scheduled-run time limit and was stopped.",
    "invalid_output": "The process returned output that the supervisor could not read as a valid result.",
    "output_limit": "The process output exceeded the supervisor's capture limit.",
    "no_result": "The process ended without a final result confirming completion.",
    "model_unknown": "The backup process reported success without identifying the model it used.",
    "fallback_unconfigured": "The backup has no valid model or positive per-run spending budget configured.",
    "credential_missing": "No OpenRouter API key was available for the backup run.",
    "credential_unavailable": "The supervisor could not retrieve the OpenRouter API key for the backup run.",
    "mode_mismatch": "The configured draft/send mode does not match the scheduled launcher's permissions.",
    "unknown_failure": "The available evidence does not identify the underlying cause.",
}


def _context(settings: Settings, diagnostic: dict[str, Any]) -> dict[str, Any]:
    context = dict(diagnostic.get("context") or {})
    context.setdefault("log_path", str(settings.log_path))
    context.setdefault("log_command", "tail -n 100 -- " + shlex.quote(str(context["log_path"])))
    return context


def _legacy(item: dict[str, Any]) -> dict[str, Any]:
    reason = item.get("reason", "unknown_failure")
    identity = item.get("identity") or {}
    provider = "OpenRouter" if identity or reason.startswith("fallback_") and reason not in ("fallback_unconfigured", "fallback_failed") else "Unknown"
    if reason in ("weekly_limit", "usage_limit") and not identity:
        provider = "Claude subscription"
    diagnostic = {
        "cause": LEGACY_CAUSES.get(reason, reason), "provider": provider, "legacy": True,
        "key_fingerprint": identity.get("key"), "workspace_id": identity.get("workspace"),
        "organization_id": identity.get("organization"), "creator_user_id": identity.get("creator"),
    }
    if item.get("status") == "fallback":
        diagnostic["provider"] = "OpenRouter"
        diagnostic["primary"] = {
            "cause": LEGACY_CAUSES.get(reason, "unknown_failure"), "legacy": True,
            "provider": "Claude subscription" if reason in ("weekly_limit", "usage_limit") else "Unknown",
        }
        diagnostic["cause"] = "unknown_failure"
    return diagnostic


def _diagnostic_action(context: dict[str, Any]) -> str:
    commands = [context.get(name) for name in ("auth_command", "config_command", "doctor_command", "log_command")]
    return "Run these read-only checks on the operator host:\n" + "\n".join(str(command) for command in commands if command)


def _repair(diagnostic: dict[str, Any], context: dict[str, Any], *, backup: bool) -> str:
    cause = diagnostic.get("cause", "unknown_failure")
    provider = diagnostic.get("provider", "Unknown")
    manifest = context.get("manifest_path") or "the operator's manifest.toml (its exact path was not captured)"
    check = _diagnostic_action(context)
    if cause in ("mailbox_read_incomplete", "assignment_read_incomplete", "discovery_evidence_invalid", "supervisor_failed", "execution_read_failed", "execution_operation_failed", "execution_phase_incomplete", "discovery_inspection_incomplete"):
        return ("Inspect the scheduled-run log and its private ordinary discovery artifact. Check mailbox connectivity "
                "and exact-thread assignment authority. Preserve legitimate human holds and all sending permissions. "
                "A model exit-zero does not establish completed work. This alert and its delivery retry use no AI model. "
                "Review existing drafts and Sent before any manual replay.\n" + check)
    if cause in ("native_task_killed", "native_task_stopped"):
        return ("Inspect the private native stream and the host Bash foreground/background lifetime settings "
                "BASH_DEFAULT_TIMEOUT_MS and BASH_MAX_TIMEOUT_MS. The structured evidence identifies interruption, "
                "not its upstream reason. Preserve incomplete required reads and existing permissions; "
                "a process exit-zero cannot establish completion.\n" + check)
    if cause == "mail_intake_failed":
        return ("Check this engine profile's connectivity, authentication and mailbox synchronization errors. "
                "The engine must support sync.run with explicit scope=email and return that scope with "
                "success=true and an empty errors array. A client timeout does not cancel engine ingestion; "
                "its synchronization lock remains held until actual work finishes. Keep paid automatic processing "
                "and sending permissions unchanged. The next scheduled tick retries this prerequisite.\n" + check)
    if cause == "fallback_unconfigured":
        return (f"Edit {manifest}: set [knobs].cron_fallback_model to a supported Claude model and "
                "[knobs].cron_fallback_budget_usd to a positive USD budget you accept. "
                f"Captured values: model={context.get('fallback_model', 'not captured')}; "
                f"budget={context.get('fallback_budget_usd', 'not captured')}. Save a funded OpenRouter API key in Desktop Settings.\n" + check)
    if cause in ("credential_missing", "credential_unavailable"):
        return ("In Desktop Settings, save or replace the OpenRouter API key for the engine profile used by this operator. "
                "This profile identifies where the key is stored, not the OpenRouter payer. "
                "If a key is already saved, diagnose the connection and authentication to that engine with the checks below. "
                "Do not paste a key into email.\n" + check)
    if cause == "mode_mismatch":
        return (f"Check the draft/send mode in {manifest} against the scheduled launcher's allowed tools. "
                f"Captured mode: {context.get('triage_mode', 'not captured')}. "
                f"Configuration error: {context.get('mode_error', 'not captured')}. "
                "Keep the intended sending authorization; correct the mismatched launch configuration.\n" + check)
    if cause == "budget_exhausted":
        if backup:
            return (f"In {manifest}, review [knobs].cron_fallback_budget_usd "
                    f"(captured value: {context.get('fallback_budget_usd', diagnostic.get('run_budget_usd', 'not captured'))} USD). "
                    "Raise that per-run budget only if the cost is acceptable, or reduce the operator's assigned workload. "
                    "Changing the engine's own AI budget will not raise this run limit.\n" + check)
        return (f"Review the scheduled Claude command's --max-budget-usd setting (captured run budget: "
                f"{diagnostic.get('run_budget_usd', 'not captured')} USD). Increase it only if acceptable, or reduce the assigned workload.\n" + check)
    if cause == "max_turns":
        return ("Inspect the last unfinished operation in the log. Reduce the assigned workload, or raise the scheduled "
                "Claude command's --max-turns limit if the additional work and cost are acceptable.\n" + check)
    if cause == "timeout":
        return ("Inspect the last operation in the scheduled-run log. Resolve a stalled external request or reduce "
                "the assigned workload so it finishes within the run time limit. The evidence does not yet identify "
                "which operation stalled; use these checks to find it.\n" + check)
    if cause in ("invalid_output", "no_result", "output_limit", "model_unknown"):
        return ("Inspect the scheduled launcher's final output in the log. It must return a valid structured final "
                "result, and the backup must report the model it used. Correct any wrapper that truncates, replaces "
                "or omits that output. The exact defect is not yet known; compare the captured result with the "
                "launcher configuration using these checks.\n" + check)
    if provider == "Unknown":
        return ("The provider and affected account were not verified. A definitive repair is not yet known; "
                "identify the actual credential source and failure before changing any billing account.\n" + check)
    if cause in ("credit_refusal", "key_limit"):
        if provider == "OpenRouter":
            if cause == "key_limit":
                return ("Open https://openrouter.ai/settings/keys in the account that owns the identified key. "
                        "Select that key and raise its spending limit if authorized, or wait for its configured limit reset. "
                        "Adding account credit alone does not raise a key spending cap.")
            return ("Open https://openrouter.ai/settings/credits in the account that owns the identified key. "
                    "Check its balance and payment method; add credit or fix the failed payment if needed. "
                    "If the balance is sufficient, inspect this key at https://openrouter.ai/settings/keys for a separate spending cap.")
        if provider == "Anthropic API":
            return "Sign in to the account that owns the identified credential and select its API organization. Open https://platform.claude.com/settings/billing there. Check available credit and payment status; add credit or fix the payment issue."
        if provider == "Claude subscription":
            return "Sign in to the identified Claude account at https://claude.ai/settings/usage. Check usage and extra-usage billing; restore the required allowance or payment there."
    if cause == "auth_failed":
        if diagnostic.get("http_status") == 403:
            return ("The provider denied access (HTTP 403); logging in again may not fix it. "
                    "Check that the identified credential has permission to use the requested model and organization. "
                    "Correct those permissions or select a model this account may use.\n" + check)
        if diagnostic.get("credential_source") == "engine_saved_openrouter_key":
            return ("In Desktop Settings for the engine profile identified below, replace the saved OpenRouter API key "
                    "with a valid key from the intended OpenRouter account. Create or check that key at "
                    "https://openrouter.ai/settings/keys. The next eligible backup attempt retrieves the saved key again; "
                    "signing into the primary Claude account does not replace this backup credential.")
        if provider == "Claude subscription" and context.get("auth_command"):
            login = str(context["auth_command"]).replace("status --json", "login")
            if login != context["auth_command"]:
                return f"On the operator host, sign in to the intended Claude account with:\n{login}\nThen verify the signed-in identity with:\n{context['auth_command']}"
        source = diagnostic.get("credential_source")
        if source in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            return (f"Replace {source} in the environment loaded by the scheduled launcher with a valid credential "
                    "for the intended provider account. Updating a key only in your interactive shell does not update the scheduler.\n" + check)
        if source == "apiKeyHelper":
            return "Repair the configured apiKeyHelper so that it returns a valid credential for the intended provider account.\n" + check
        return "Replace the expired or rejected credential in the source used by the scheduled process. Use these checks to locate that source and verify the account; never email the credential.\n" + check
    if cause in ("rate_limit", "quota"):
        action = f"Wait for the provider's allowance to reset (captured reset: {diagnostic.get('reset_at', 'not reported')}). "
        if provider == "Claude subscription":
            action += "Check the signed-in account and reset time at https://claude.ai/settings/usage. "
        elif provider == "OpenRouter":
            action += "Check the identified key's allowance at https://openrouter.ai/settings/keys. "
        else:
            action += "Check the usage quota for the identified provider account. "
        return action + "If this repeats, reduce scheduled workload or increase that account's allowance where available.\n" + check
    if cause == "provider_unavailable":
        return "Allow the next scheduled attempt to retry after the provider recovers. If failures continue, inspect the captured error and configured provider using these checks:\n" + check
    return ("A definitive repair is not yet known. Inspect the captured process result and scheduled-run log with the checks below. "
            "For a turn or time limit, inspect the last unfinished operation and reduce the assigned workload if it cannot fit. "
            "For rejected requests or unreadable results, use the recorded error code and launcher configuration to locate the failing request or output contract.\n" + check)


def _detail(settings: Settings, diagnostic: dict[str, Any], *, backup: bool, completed: bool = False) -> str:
    context = _context(settings, diagnostic)
    cause = diagnostic.get("cause", "unknown_failure")
    lines = [] if completed else ["Cause: " + CAUSES.get(cause, CAUSES["unknown_failure"])]
    if not completed and cause == "auth_failed" and diagnostic.get("http_status") == 403:
        lines = ["Cause: The provider denied access (HTTP 403). This may be an account or model permission restriction."]
    lines.append("Affected provider: " + str(diagnostic.get("provider") or "Unknown"))
    for field, label in (("account_email", "Provider account email"), ("organization_id", "Provider organization ID"),
                         ("workspace_id", "Provider workspace ID"), ("creator_user_id", "Provider key creator user ID"),
                         ("auth_method", "Authentication method"), ("credential_source", "Credential source")):
        if diagnostic.get(field) and diagnostic[field] != "unavailable":
            lines.append(f"{label}: {diagnostic[field]}.")
    key = str(diagnostic.get("key_fingerprint") or "not captured")
    if key != "not captured" and not any(marker in key for marker in ("…", "...", "hidden", "***")):
        key = "[credential identifier hidden]"
    if key not in ("not captured", "unavailable"):
        lines.append(f"Masked provider key: {key}.")
    account_known = any(diagnostic.get(field) not in (None, "", "unavailable") for field in
                        ("account_email", "organization_id", "workspace_id", "creator_user_id", "key_fingerprint"))
    technical_health = cause in (
        "mailbox_read_incomplete", "assignment_read_incomplete", "discovery_evidence_invalid",
        "execution_read_failed", "execution_operation_failed", "execution_phase_incomplete", "discovery_inspection_incomplete", "supervisor_failed", "native_task_killed", "native_task_stopped")
    if not account_known and not technical_health:
        lines.append("The affected provider account could not be identified from the captured evidence.")
    for field in ("exit_code", "http_status", "error_code", "terminal_reason", "session_id", "time_utc", "reset_at", "limit_window", "key_limit_remaining", "key_limit", "run_budget_usd"):
        if diagnostic.get(field) is not None:
            lines.append(f"{field}: {diagnostic[field]}")
    if diagnostic.get("legacy"):
        lines.append("This queued notice predates detailed diagnostics. Historical process and account evidence was not captured.")
    if completed:
        return "\n".join(lines)
    repair = _repair(diagnostic, context, backup=backup)
    if not account_known and not technical_health:
        repair += "\nIdentify the provider account before changing billing or credentials."
        if _diagnostic_action(context) not in repair:
            repair += "\n" + _diagnostic_action(context)
    lines += ["", "Action to repair", repair]
    return "\n".join(lines)


def render(settings: Settings, item: dict[str, Any]) -> tuple[str, str, str]:
    """Return equivalent plain and escaped HTML messages, including legacy entries."""
    kind = item.get("status")
    diagnostic = item.get("diagnostic") or _legacy(item)
    primary = diagnostic.get("primary") or item.get("primary")
    context = _context(settings, diagnostic)
    if kind == "primary":
        subject = "INFO: scheduled assistant model changed" if item.get("model_only") else "RESOLVED: scheduled assistant completed using its main service"
        body = "Symptom: Resolved. The scheduled assistant completed this run using its main service.\nCause: The reported model changed." if item.get("model_only") else "Symptom: Resolved. The scheduled assistant completed this run using its main service again.\nCause: The current run succeeded; this does not establish what repaired the earlier failure."
        body += "\nAction to repair: No action is needed for this completed run.\n" + _detail(settings, diagnostic, backup=False, completed=True)
    elif kind == "fallback":
        subject = "INFO: scheduled assistant completed using its backup service"
        body = ("Symptom: Completed. The backup service completed this run; current work is not blocked. "
                "No action is needed to complete this run.\n\nRestore the failed main service\n" +
                _detail(settings, primary or diagnostic, backup=False))
        if primary:
            body += "\n\nWorking backup provider: " + str(diagnostic.get("provider", "Unknown")) + "\n" + _detail(settings, diagnostic, backup=True, completed=True)
    else:
        provider = diagnostic.get("provider") or "Unknown"
        summary = SUBJECT_CAUSES.get(diagnostic.get("cause"), SUBJECT_CAUSES["unknown_failure"])
        subject = f"ACTION REQUIRED: assistant stopped — {provider} {summary}"
        body = "Symptom: Stopped. This scheduled run is not confirmed complete; pending work may be delayed.\n\n"
        if primary:
            body += "Repair options: fixing the main service alone can restore the next scheduled run. Repairing the backup is an alternative when the main service remains unavailable and backup execution is eligible. Both repairs are not required to resume.\n\nFailed main service\n" + _detail(settings, primary, backup=False) + "\n\nBackup failure\n"
        body += _detail(settings, diagnostic, backup=bool(primary) or str(item.get("reason", "")).startswith("fallback_"))
        if diagnostic.get("no_work_proven"):
            body += "\n\nThe supervisor confirmed that this attempt did no work."
        else:
            body += "\n\nSome actions may already have happened. Review recent sent messages and drafts before manually repeating work; the failed run was not automatically replayed."
    body += ("\n\nAfter repair\nOrdinary account or payment repairs require no daemon restart or manual replay. "
             "The next scheduled tick will try the main service again if scheduling is enabled and the assistant is not paused. "
             "A new attempt does not guarantee recovery until the cause is fixed.")
    if context.get("status_command"):
        body += "\nVerify scheduling and pause state on the operator host:\n" + str(context["status_command"])
    body += (f"\n\nOperator workspace: {context.get('workspace') or settings.company_name or settings.slug or 'unknown'}."
             f"\nNotice recipient: {settings.email_address} (not evidence of the provider billing account)."
             f"\nEngine profile UID: {context.get('engine_owner_uid') or 'not captured for this attempt'} (credential storage profile, not provider payer)."
             f"\nScheduled-run log: {context['log_path']}."
             f"\nAI model: {item.get('model') or 'not reported'}."
             f"\nNotice code: {kind or 'unknown'}/{item.get('reason') or 'none'}.\n")
    rich = html.escape(body).replace("\n", "<br>")
    for url in OFFICIAL_REPAIR_URLS:
        rich = rich.replace(url, f'<a href="{url}">{url}</a>')
    return subject, body, "<p>" + rich + "</p>"
