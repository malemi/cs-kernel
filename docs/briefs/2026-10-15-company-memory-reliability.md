---
date: 2026-10-15
status: draft
kind: incident-brief
---

# Company memory: failed reads and unreliable factual synthesis

## Problem and intent

An interactive, read-only company-context investigation in the Café 124 clone
found that the normal memory-question path was unavailable on the default
profile and produced unreliable synthesis on another authorized company profile.
The operator needs an agent that can learn the company from its records without
having to reconstruct and correct that knowledge personally each session.

This brief records observed failures and the investigation needed. It does not
establish corrupted stored memory, prescribe a repair, or authorize implementation.

## Observed evidence — 15 October 2026

Commands ran from `/home/mal/124/124-cs` using `.venv/bin/python -m cs`.
`cs memory` reported engine reachability; `cs whoami` and the equivalent command
for `mario.alemi@cafe124.it` authenticated both declared profiles. Reachability
and authentication did not establish that memory questions worked.

1. **Default profile questions failed, including a short thematic question.**
   Production-method and company-brand/channel questions through `cs ask`
   returned exit 4 with these observed errors:

   ```text
   engine error: INTERNAL_ERROR: AI paused: OpenRouter request exceeds the supported context bound.
   engine error: INTERNAL_ERROR: K3 Chat request exceeds supported context bound.
   ```

   These are failed engine turns, not empty search results. Provider/model
   attribution beyond the error strings was not independently diagnosed.

2. **The secondary profile returned an overconfident company reconstruction.**
   `cs --account mario.alemi@cafe124.it ask '…'` answered questions about
   technology, production, people, products and markets. Its synthesis included
   unsupported certification/partnership claims and treated several formats as
   available despite narrower current records. It described the patent as
   granted without supplying a grant document. These assertions were not
   accepted as facts. The investigation did not inspect the underlying entity
   blobs, so it cannot locate the error in storage, retrieval or generation.

3. **A focused follow-up recovered a useful original.** It cited Ivan's
   4 October email describing cold extraction, two filtration stages and gentle
   pasteurisation of filled cans. The thread was subsequently read through
   `emails.list_by_thread` and confirmed that statement. Thread:
   `<CAJ1mzbGNjyvm+m8FyFTiCLO0bnxgwk-w77VvMzLA9Bppiw0SeA@mail.gmail.com>`.
   Retrieval therefore worked in at least this bounded case; universal memory
   failure would be an unsupported conclusion.

4. **Independent records exposed errors and temporal conflicts.** The original
   patent receipt states 25 July 2025, whereas the Drive company summary states
   24 July. The pricing project updated 14 October restricts bought-in
   concentrate products to tests, superseding their commercial presentation in
   a 5 October business plan. A 14 October Jacobacci email distinguishes the
   international search opinion's findings on process and beverage claims;
   it does not itself establish a granted patent.

5. **Company orientation was also incomplete.** The available clone bootstrap
   was `cs-capabilities`. Its initial procedure load omitted an existing Drive
   company profile and index. Subsequent authorized research read
   `CAFE124/AGENT/AZIENDA.md` (`1tFXtgFn5I4OSuiJUJeLTMMcM-xZSl-0T`) and
   `AGENT/index.md` (`1VtCzgXFzE5lYHQMa3sJelNY27tZjiDV3`). Thus an index existed;
   the agent had not discovered it during initial loading. This is a separate
   orientation problem, not proof of an engine-storage defect.

## Scope, ownership and constraints

- Diagnose engine request construction, context bounds, retrieval and factual
  synthesis at the engine layer. The kernel must not create a competing entity
  memory or compensate with company-specific heuristics.
- Assess bootstrap navigation separately, including the planned `cs-bootstrap`
  route. Preserve company-owned sources and their dates and authority.
- Keep failures distinct from absence, proposals from approved offers, and
  prospects from established relationships.
- No memory reset, rewrite, provider change, sync, publication or customer
  action is authorized by this brief. The research did not read `cc-memory`;
  the operator explicitly endorsed that exclusion. Its usefulness or quality
  is not an incident finding.

## Proposed acceptance for subsequent work

Authenticated, ordinary read-only questions must succeed on the affected
profiles or return a precise actionable failure. Repeated focused questions
must be compared with the same original documents and messages: material claims
need traceable evidence, conflicting dates/scopes must remain visible, and
unsupported facts must not become confident company knowledge. Bootstrap
coverage must state what was actually loaded and expose the existing company
index. Preserve source records and demonstrate the repair on the real query
path; reachability checks alone are insufficient.

## Evidence limits and open diagnosis

This is a report from the current conversation and its actual command outputs,
not a retained raw runtime bundle. No additional files or company memories were
saved during that research. Some broad result sets were truncated; the inquiry
was selective, not a complete archive audit. Exact request sizes, selected
models, server history binding, stored entity contents and grant status remain
unverified. No causal attribution or repair is claimed.
