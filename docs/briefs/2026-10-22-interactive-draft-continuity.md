# Interactive draft continuity

## Intent

The operator requires useful work to continue when assignment observations or a
human takeover prevent sending: prepare a review draft, never silently stop.
Interactive draft preparation currently auto-selects an undeployed engine policy;
the hosted engines support released generic chat and scoped assignment drafts,
but not supervised-review or contextual-email policy v1.

## Scope and constraints

Repair interactive `draft-reply` negotiation and source-validated review copies
in the kernel, then adopt the bounded change in the requesting clone. Preserve
unrelated dirty edits. Scheduled callers keep their current scoped assignment,
capability, workset and send checks. Exact-ID sending remains unchanged: a held
thread may produce a draft, not an automatic send. No assignment mutation,
privileged signing, public release, engine restart or wholesale package rollback.

An interactive prepare request may use the released generic engine draft path
when the engine does not advertise supervised-review support. Select the route
before generation, never retry a failed effect using another policy. Validate
own-mailbox source, requested original, exact RFC thread, recipients and returned
draft identity; no local model composition or SMTP. Label the legacy route as
human review, without claiming engine-enforced source scope. Deny send approvals
for all preparation calls. Preserve existing Gmail edits/copies and verify mirrors.

## Acceptance

- An assignment-held interactive request prepares a real engine draft/review copy
  on a policy1-only hosted engine; no send occurs during preparation.
- A supported newer engine retains its supervised-review contract.
- Unknown/malformed capability contracts and missing/foreign source or mismatched
  output fail visibly; no guessed identity or duplicate provider mirror.
- Scheduled routing and sending retain existing holds and exact-ID approval rules.
- Meaningful wire/command/negative tests pass; baseline suite failures are reported.
- Requesting clone uses the verified bounded code and at least one requested
  customer draft is independently read back, subject to live engine availability.

## Assumptions

The operator's latest clarification authorizes draft-only work on human-held
contacts, not removal of sending guards. Ordinary generic engine chat is an
existing interactive contract. Real sends remain authorized only where current
send checks allow them. Provider work is bounded to the already requested cases.
