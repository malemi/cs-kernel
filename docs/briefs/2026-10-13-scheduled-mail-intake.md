# Scheduled mail intake before operator generation

## Intent

Make independently delivered new email available in the engine before the ordinary scheduled operator starts its model. Real acceptance found fresh originals in Gmail but absent from engine storage while AUTO_UPDATE_ENABLED was disabled. Both maintained clones need this prerequisite.

## Scope and ownership

The kernel owns one deterministic prerequisite in cs/operator_recovery.py after permission validation and before primary identity/model execution, plus focused tests in tests/test_operator_recovery.py. The separately owned engine change adds validated sync.run scope=email; omitted scope preserves existing behavior. Its typed reply echoes scope=email, a boolean success and an errors array. The kernel rejects absent or different echoes, malformed responses and unsuccessful results. No legacy call with an ignored parameter is acceptable.

Run intake once per ordinary run, shared with fallback. Check CS_PAUSE before intake and again before model launch. Use authenticated Settings-owned engine identity. Preserve paid auto-update settings, model budgets, permissions, send guards, company rules, WhatsApp, banking and the intentional MCP overlay. Do not use update.run or catchup. This performs email synchronization only, without paid generation/classification.

## Constraints

Bound the kernel waiting interval, authentication and cleanup explicitly. A client timeout does not cancel server work; the engine owns serialization that remains effective while actual ingestion continues. Never claim whole-server cancellation from a client deadline. Intake failures stop model launch, return nonzero and produce a credential-free actionable owner notice. Exact candidate body availability remains an existing generation prerequisite: success does not certify every folder or message was ingested. Missing evidence remains UNKNOWN.

## Acceptance

Focused checks prove ordering, exactly one intake across primary/fallback, no intake for invalid permissions or pause, pause during intake prevents model launch, and no model launch on legacy/malformed/failed/timed-out intake. Preserve existing recovery and notice tests. Run the kernel suite after implementation. Review the integrated frozen kernel and both actual engine runtime families before live work.

Real acceptance uses ordinary cron with paid automatic update disabled and independently delivered fresh originals; no manual synchronization, fixture storage injection or canned model output. Require actual exact originals in engine storage, natural MrCall reply, Cafe draft/no-send, signup policy, acknowledgement/no-loop, terminal results and independent cleanup. Retain failed earlier runs. Documentation closure and a separate final review precede baseline advancement. Publication requires separate authorization.

## Assumptions and rollback

The additive engine contract is reviewed and installed before selecting this kernel candidate. Unavailable capability stops safely. Roll back only this prerequisite and its selected candidate after cleaning owned live work; do not revert concurrent engine/MCP work or unrelated kernel changes.
