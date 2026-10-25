# Bound repeated review and assignment reads

## Intent

Finish the authorized exact-draft operational verification by fixing the measured
review stall. The configured Café review took about 11 minutes 49 seconds and
its first 110-second invocation returned no JSON. Preserve every customer row,
engine-owned judgement and assignment/send boundary while reducing repeated
connection and serial-read overhead.

## Evidence and scope

`cs/review.py` projects every listed assignment serially, then performs a full
14-day unanswered sweep. `task_assignment.projections` projects every root
serially across configured peers; `engine_view.classify` also opens a fresh RPC
connection per root. The existing single-root validation and peer merge define
the authority contract and must remain the common implementation.

Kernel ownership: `cs/review.py`, `cs/task_assignment.py`,
`cs/engine_view.py`, one new read-only RPC batching helper
`cs/rpc_reads.py`, and focused existing/new tests. No server API, dependency,
credential, permission, model, sender, company procedure or persistent ledger
change. Preserve concurrent notice work and the separately reviewed optional
native-discovery transport. Guidance remains owned by that existing workstream.

Use the existing multiplexed EngineClient, one connection per selected account
batch and at most four concurrent read requests. Permit only the existing
`tasks.assignment.project` and `emails.list_by_thread` methods. Define an explicit
batch deadline and retain the existing per-request bounds. Authentication retains
its existing bounded refresh and identity checks; connection/close cleanup is
part of verification, not a claimed instantaneous operation.

Preserve deterministic input/result order, every requested root and all completed
observations. Timeout, unreadable peer, malformed response or unknown company
scope remains explicit UNKNOWN/held evidence. Never use a prior successful
response as current authority, infer absence, skip held customers or prioritize
fixtures by changing business decisions.

## Acceptance

- Unchanging controlled primary/peer responses produce the same classification,
  projection, provenance, hold/conflict/closed/later-inbound and row ordering as
  the original implementation. Single-root callers retain their public contract.
- Real local WebSocket integration proves one connection per account, at most
  four active reads, unique correlation, bounded stalled requests, cancellation
  and no orphan client readers. Missing/unstarted roots remain visible UNKNOWN;
  wrong owner/space/revision/coverage and peer disagreement still refuse action.
- The helper rejects mutation methods before connection and never invokes an LLM.
  Existing authentication, mailbox SELF/dedup and sender guards are unchanged.
- Focused semantic checks and the full kernel suite pass. Read-only live review
  on both configured clones measures actual stage timing and verifies complete
  JSON with explicit degradation, without sending, composing or manual sync.
- Fresh brief, plan and source reviews precede integration. Combined review with
  the discovery transport and Desktop consumer precedes the one final genuine
  three-job acceptance. Failed evidence is retained; no acceptance waiver,
  resealing, release or baseline advancement follows from latency improvement.

## Limits

This targets repeated serial RPC reads. It does not promise a universal 90-second
whole-review duration: provider reads, settlement and campaign stages retain
separate existing bounds. Record actual latency and remaining errors honestly.
