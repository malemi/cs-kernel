# Company customer-service playbooks

## Problem

`cs-triage-mail` owns how the operator answers customers, but some support
decision trees are company-specific: which product endpoint to test, which
internal team receives an incident, and which approved non-mail diagnostic may
be used. Putting those rules in engine `USER_NOTES` mixes operational procedure
with voice and writing policy. Putting them directly in the shared skill leaks
one company's product mechanics into every clone.

## Decision

The shared skill reads an optional clone-owned
`company/customer-service-playbook.md` before deciding or composing. The
playbook may require evidence and a separately approval-gated non-mail action;
it cannot widen mail sending or tool approvals. Headless denial leaves the task
open with a concrete operator action.

The physical rendered skill remains under `.claude/skills`; Codex and OpenCode
resolve the same bytes through `.agents/skills` and `.opencode/skills`. The
playbook is therefore one company procedure used by all supported agents.

## Acceptance

- A rendered `cs-triage-mail` discovers the optional playbook.
- Claude Code, Codex and OpenCode resolve the identical rendered workflow.
- The kernel contains no company-specific support procedure.
- Existing draft/send and approval boundaries remain in force.
