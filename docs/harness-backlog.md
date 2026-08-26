# Harness Backlog

Enforcement / tooling gaps: what check is missing and what class of error it
would prevent. Delete an entry as the enforcement lands.

- [ ] **Nothing stops a tag shipping over a red suite** — Discovered:
  2026-07-27, narrowed 2026-07-30 — gate 1 was red at every tag `v0.3.1` …
  `v0.3.7` and they all shipped anyway. The gate itself is FIXED as of
  `v0.4.0` (literal purged, pattern widened to the operator's name/mailbox,
  plus gate 12 rendering every template and sweeping the output), so the
  suite is 12/12 green — but the missing enforcement is unchanged: no release
  step refuses to tag while `bash tests/run.sh` exits 1. A pre-tag hook or a
  `make release` that runs the suite first would close it.

- [ ] **Nothing verifies that a clone's pin is actually installed, or that the
  three pin sites agree** — Discovered: 2026-07-27 (`mrcall-cs`) — that clone ran
  for days with `requirements.txt` and `manifest.toml` at one tag while
  `requirements.lock` still named the **`v0.3.2`** commit; a venv rebuilt from the
  lock would have had neither the threading headers nor `thread_with()`, i.e. a
  loop that opens a new thread per reply and cannot read a customer's body. A
  `cs doctor`-style check (all three pin sites equal, and equal to what is
  installed in the venv) would have caught it instantly.

- [ ] **Running any `cs` command with the CWD inside this repo silently bypasses
  the pin** — Discovered: 2026-07-27 — Python puts the CWD on `sys.path`, so `cs`
  resolves to `./cs/` (the source tree) rather than the clone's pinned install,
  and a stale `cs_kernel.egg-info/` makes `importlib.metadata.version('cs-kernel')`
  report an old version with total confidence (observed: `0.3.4` while the venv
  held `0.3.7`). It cost a real diagnostic detour. The cron wrappers `cd` into the
  clone so production is unaffected, but this is exactly the "a clone cannot drift
  a package whose source it does not hold" guarantee failing for a human at a
  prompt. Enforcement idea: keep the build artifacts out of the working tree, or
  have `cs whoami` print the resolved package path alongside the version.

- [ ] **The reply-check treats autoresponders as human replies**
  (`campaign._inbound_since`, used by `send_reminder` + `send_sms`) — Discovered:
  2026-07-22, still open — an out-of-office or "casella disabilitata" auto-reply
  counts as "they replied", so the kernel silences both the SMS nudge and the
  daily reminders for that contact. It hit two dead mailboxes in the batch-2
  campaign, where SMS was the only channel that still reached them. `mrcall-cs`
  worked around it with a machine-detector in its own campaign prompt, which is
  clone-local prompt text, not a kernel capability. The fix belongs here:
  LLM-classify the newest inbound (human vs autoresponder/NDR) before treating it
  as a reply. Verified still open on 2026-08-26 — `_inbound_since`
  (`cs/campaign.py:113`) returns `gmail_archive.inbound_since` unfiltered. The
  classification no longer has to be built: the engine answers it
  (`is_auto_reply` on `emails.list_by_thread`, and `emails.needs_reply` since
  `v0.26.0`), which is also the only place charter invariant 4 allows it to live.

## Oversized docs — reviewed

Verdicts recorded for every document the gate's size advisory names. `split` is
work and gets its own `OPEN` entry above; `keep whole` carries its reason.

| doc | lines at review | verdict | date |
|---|---|---|---|
| docs/execution-plans/2026-07-28-eternal-operator-loop.md | 631 | keep whole — one argument, read start to finish when the plan is unblocked | 2026-08-26 |
| docs/sessions/5df6e400-9157-4214-8267-426c0ebea560.md | 560 | keep whole — gitignored per-session scratch, not repository knowledge | 2026-08-26 |
| README.md | 465 | keep whole — the clone-onboarding manual, read by section | 2026-08-26 |
