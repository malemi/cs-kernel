# Brief — engine failures are reported as success by every chat-path verb

## Intent

`cs ask` prints an engine error and exits 0. So does `cs draft-reply`. The
engine returns failure *inside* a successful JSON-RPC result, and the CLI reads
only the human-readable field, so a caller — a script, a skill step, the cron
tick — cannot distinguish an answer from an outage.

Make a failed engine turn fail visibly, at the CLI boundary, without changing
what a successful turn does.

## Why this is not a cosmetic defect

`cs ask` is the primary source for any fact that leaves the desk inside a
message (`124-cs/CLAUDE.md` § 9). On the `124-cs` clone it has been failing on
the `production@cafe124.it` profile with a context overflow that grew over time
— `~/.124-cs/cs_operator.log` records 214,065 tokens, then "~240–284k", then
276,181, and 647,427 today.

The grounding step therefore failed while the compose step
(`cmd_draft_reply`, `cs/cli.py:1222`, same `rpc.chat` path) kept succeeding,
because a single-thread compose instruction matches far less retrieval than a
broad question. The operator identity kept producing fluent, confident replies
built on no retrieved precedent — reported by the operator as answering "senza
guardare le mail passate".

**The exit code is why this ran for months without escalation.** Every tick
recorded the failure in prose — *"blocca il grounding del triage"*, *"è il
motivo per cui non ho potuto fondare la risposta a Bitossi"* — and every tick
exited 0. A defect that reports itself as success is one no monitor can catch,
and any future fix to the engine can regress the same way, silently.

## The mechanism, verified

Captured live from the engine (credits currently exhausted, which produces the
same failure shape as the overflow):

```json
{
  "result": {
    "response": "I encountered an error processing your message: MrCall proxy error (502): ...",
    "tool_calls": [],
    "metadata": {
      "execution_time_ms": 912.89,
      "error": "INTERNAL_ERROR",
      "error_detail": "MrCall proxy error (502): upstream_error: anthropic_upstream: {...}"
    },
    "session_id": null
  },
  "approvals": [],
  "notifications": []
}
```

`result.metadata.error` is a machine-readable code and `result.metadata.error_detail`
carries the message. `cmd_ask` (`cs/cli.py:1145-1157`) reads only
`res.get("response")`, prints it to **stdout**, and ends with a hardcoded
`return 0` (`:1157`). The error text is therefore indistinguishable from an
answer both by exit code and by stream.

## Scope

- `cs/cli.py` — `cmd_ask` (`:1145`), `cmd_draft_reply` (`:1202`), and every
  other verb reading a `rpc.chat` result. **The plan must enumerate them; the
  brief does not assume the list is two.**
- Possibly one shared helper, if more than two verbs need identical handling —
  the extend-before-you-build target is whatever already unwraps a chat result,
  not a new parallel unwrapper.

Out of scope:

- The engine-side prompt-token budget that causes the overflow. Engine-owned
  (`124-cs/CLAUDE.md` § 0b); this brief makes its failures visible, it does not
  fix them.
- The credit exhaustion. Operational.
- Retry, fallback, or degradation logic. Reporting the failure is the whole
  change; deciding what to do about it belongs to the caller.

## Constraints

- **A successful turn is byte-identical on stdout and still exits 0.** Any
  consumer parsing `cs ask` output today must be unaffected.
- **Error text goes to stderr, not stdout.** Today the error is printed to
  stdout where an answer belongs, so a caller capturing stdout stores the error
  as if it were content. This is half the defect and fixing only the exit code
  leaves it.
- **Do not re-derive "did it fail" from the response prose.** Keying on the
  `"I encountered an error"` prefix would be a second implementation of a
  judgement the engine already publishes in `metadata.error` — the pattern
  `124-cs/CLAUDE.md` § 0b bans. Key on the structured field.
- **The exit code is a contract change and must be surveyed before it lands.**
  A non-zero `cs ask` could abort a cron tick or skill step that currently
  continues past a failed grounding query. The plan must find every caller —
  `bin/cs_operator_cron.sh`, `.claude/skills/**`, and their `.j2` templates —
  and state for each whether aborting is the wanted behaviour. Where it is not,
  the caller is what changes, deliberately; the verb still tells the truth.

## Acceptance criteria

1. A chat-path verb whose result carries `metadata.error` exits **non-zero** and
   writes `error` and `error_detail` to **stderr**.
2. A successful turn's stdout and exit code are unchanged, asserted by a test.
3. No verb decides failure from the text of `response`.
4. Every caller of an affected verb is enumerated, and each is either confirmed
   correct under a non-zero exit or changed deliberately in the same milestone.
   The cron's draft-only deny set (`bin/cs_operator_cron.sh`) is unchanged.
5. A test covers the captured failure payload above — the fixture is the real
   engine shape, not an invented one.

## Open question for the plan

Whether the exit code should distinguish *kinds* of engine failure (transport
down vs. prompt rejected vs. upstream billing) or whether one non-zero code
suffices. One code is simpler and sufficient for "did this succeed"; distinct
codes would let the cron continue past a billing outage while stopping on a
malformed request. Decide with evidence from the caller survey, not by
preference.
