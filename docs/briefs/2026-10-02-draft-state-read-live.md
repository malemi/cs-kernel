# Draft state is read live, never recalled

## Problem and outcome

An assistant working a clone told its operator that a draft existed when it did
not. In 124-cs, on 1 and 2 October 2026, it said twice that engine draft
`e720e548` (a superseded quote to a prospect) was "still in Gmail Drafts" and
had to be deleted. The operator reported that the draft was not there.

The error had two causes:

1. **No check.** On 2 October the claim came from the assistant's own session
   notes, written the day before. In the meantime the team had dealt with the
   draft themselves.
2. **The wrong check.** On 1 October the assistant had run
   `cs rpc drafts.list`, which lists engine rows, and reported the result as a
   fact about Gmail. An engine row outlives a send or a deletion made in Gmail.
   This is failure mode 2 of `2026-09-16-exact-draft-identity.md`: "a
   Gmail-side send leaves the engine row `status=draft` and apparently
   sendable".

The kernel already has the right check. `cs review --json` reconciles Gmail
Drafts, the engine rows and Gmail Sent. It gives every logical draft a verdict
(`ready`, `overtaken`, `superseded`, `duplicate`) with both handles. Nothing
makes an assistant use it before speaking.

**Outcome:** in every clone, an assistant states a draft's existence, content,
location or verdict only as a `cs review` run in the same turn reports it. This
holds whichever model runs the session, because a mechanical guard enforces it
rather than the model's recall.

## Scope

1. **Charter rule.** Add to the `AGENTS.md.j2` safety section:
   - never state a draft's existence, content, location or verdict that
     `cs review` did not report in the same turn;
   - an engine `drafts.list` row is not evidence that a draft is pending;
   - memory and session notes record a draft as an event (handle, created at,
     recipient), never as its current state.
2. **Mechanical guard (Claude Code).** A kernel-owned check wired as a Stop
   hook in `.claude/settings.json.j2`. It reads the turn from the hook's
   transcript, which is local only: no engine call. It blocks a final reply
   that names a draft handle unless the same handle appears in the output of a
   `cs review` call made in that turn. The block reason tells the model to run
   `.venv/bin/python -m cs review --json` and report its verdicts.
   - The handles to recognize are the full engine id, the short engine prefix
     the kernel prints, and the Gmail uid.
   - The exact detection rules belong to the plan.
3. **Skill consistency.** Check that no skill reports draft state from
   memory, tasks or `drafts.list` alone. That covers at least `cs-review`,
   `cs-triage-mail`, `cs-campaign-tick` and `cs-help`.

Out of scope: exact draft identity, external-send reconciliation and retiring
stale rows. Those belong to the active `2026-09-16-exact-draft-identity` plan,
and nothing here changes pairing or verdict logic.

## Constraints

- **Ownership:** template-owned files change only here. Clones receive the
  change through a release and `cs update`.
- **Read-only:** the guard never creates, edits, sends or deletes a draft.
- **No false blocks on:**
  - command names such as `cs draft-reply` or `cs draft-send`;
  - generic discussion of drafts;
  - git short hashes and other hexadecimal ids;
  - a handle that the turn's own `cs review` output contains.
- **No loops:** a blocked reply gets one clear instruction. After a `cs review`
  call, the same reply passes.
- **Cost:** the guard reads the transcript only. `cs review` itself took 77.7 s
  for 80 drafts in 124-cs on 2026-09-30. It runs when a draft is about to be
  discussed, never on every turn.

## Acceptance

- The rendered clone `AGENTS.md` carries the rule, and a template test covers
  it.
- Guard tests on transcript fixtures:
  - a handle with no review in the turn: blocked;
  - a handle present in the same turn's `cs review` output: passes;
  - a handle present only in `drafts.list` output: blocked;
  - a handle present only in an earlier turn's review: blocked;
  - `cs draft-reply` mentioned without a handle: passes;
  - a git short hash in the reply: passes.
- The settings template wires the hook, and a rendered clone runs it in a smoke
  test.
- **Live check in a clone:** asked "which drafts are pending?", the assistant
  starts from `cs review --json` and quotes its verdicts.

## Material assumptions (verify in the plan)

- **Claude Code Stop hook:** its input includes `transcript_path`, and a
  `block` decision with a reason makes the model continue instead of ending the
  turn. Check this against the current Claude Code hook documentation.
- **Codex:** it has no equivalent stop hook, so the charter rule is its only
  guard. Record this as a known gap if it is confirmed.
- **Handle shapes:** the formats that `cs review` and the draft verbs print
  (full id, short prefix, Gmail uid) are stable enough to match precisely.
  Confirm them in the review renderers.

## Evidence

- 124-cs session notes `docs/sessions/f64e7233-e42c-47c7-98a9-afacfcc9df05.md`.
- 124-cs `docs/active-context.md`, which records the diverging Gmail and engine
  draft counts.
- `docs/briefs/2026-09-16-exact-draft-identity.md`, failure mode 2.
