# Harness Backlog

Enforcement / tooling gaps: what check is missing and what class of error it
would prevent. Delete an entry as the enforcement lands.

- [ ] **Gate 1 has been red since `v0.3.0` and nothing stops a tag shipping over
  it** — Discovered: 2026-07-27 — `bash tests/run.sh` exits 1 on
  `cs/templates/project/CLAUDE.md.j2:52` (`desktop.mrcall.ai`, `mrcalld`,
  `/run/mrcalld/<uid>.sock`), yet `v0.3.1` … `v0.3.7` all shipped. A suite whose
  failure is routine stops being read: gates 2–10 could go red tomorrow and the
  `RESULT: FAIL` line would look exactly the same as it does today. Two things are
  missing — the fix itself (those values are manifest fields), and a release step
  that refuses to tag while the suite is red.

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
  as a reply.
