# Operator and engine AI boundaries

The CTO's model-cost question was answered as if all AI work used the Desktop
engine. In fact, clone cron wrappers launch Claude Code headlessly and drive
engine RPCs; kernel-side direct classifiers form a further API path. Existing
entry indexes do not make model, billing and pause boundaries obvious. The hb
Desktop checkout also trails released main, exposing stale architecture docs.

Update hb, Desktop and cs-kernel entry indexes, existing architecture/setup and
spending references. Put a concise distinction at entry and detailed controls
in the owning repository. Preserve current automation, credentials, models,
code and company-specific send policies. Explicitly distinguish headless Claude
Code from a headless engine daemon; engine API work triggered by the operator
still uses the engine's own billing and daily cap. Never promise that one pause
or budget covers all three AI execution paths. Date operational observations.

Repair the stale Desktop checkout only after backing up and comparing local
work against released content. Preserve unrelated work. This is documentation
repair, not a model migration, a kernel release or an automation restart.

Acceptance: a reader entering any of the three indexes can identify where
Claude Code runs, who selects/pays for each model, which pause applies, and
where to inspect exact runtime evidence. Verify against wrapper/CLI/RPC source;
run documentation gates and an independent semantic review. No paid LLM calls.
