---
doc_baseline_commit: 60d9fc5
doc_baseline_date: 2026-07-30
---

# Active Context — cs-kernel

Volatile state for the shared kernel of the `<company>-cs` operators. The
durable reference is [`CLAUDE.md`](../CLAUDE.md) (the anti-fork charter, layout,
release rules) and [`CHANGELOG.md`](../CHANGELOG.md) (what each tag changed and
which clones must re-collaudo). Pruned history lives in
[`active-context-archive.md`](active-context-archive.md). This file tracks only
what is *current*.

## State now

- **Latest release tag: `v0.8.1`. Current HEAD status: untagged.**
  `v0.8.1` is the corrective for `v0.8.0` (2026-08-19), which was tagged and
  pushed straight from the feature commit and therefore installs as `0.7.1` —
  the fifth entry in `TAG_VERSION_EXCEPTIONS`, object pinned immutable.
  `v0.8.1` is the same code under its true number.
- The repo is **public** at `github.com/malemi/cs-kernel` — the single origin.
  The old private `hahnbanach/cs-kernel` is archived; the clone guide points
  at the public one.
- Clone matrix (source: Phase B handoff, meta-repo
  `docs/execution-plans/2026-08-19-phase-b-session-handoff.md`; the
  `mrcall-cs` pin verified in its `requirements.txt`):

  | Clone | Pinned | Collaudo | Operator |
  |---|---|---|---|
  | `mrcall-cs` | `v0.7.1` | static — signed 2026-08-16 | un-paused, ticking |
  | `124-cs` | `v0.7.1` | static — signed 2026-08-16 | un-paused, ticking |

- The kernel runs per-invocation from each clone's venv (no long-running
  kernel process). The provider side is the mrcall-desktop daemons, deployed
  at `d239e5f` (2026-08-03).
- Tagging procedure the release gate imposes: the release commit itself claims
  `Latest release tag:` + `Current HEAD status: tagged as` for the new
  vX.Y.Z, so the gate is red in the gap — commit, tag immediately, verify the
  gates AT the tag. The first post-tag commit flips the HEAD status back to
  untagged and pins the tag's commit id in `IMMUTABLE_TAG_TARGETS`
  (`tests/test_release_consistency.py`).
- Shipped in `v0.8.0`/`v0.8.1` (MINOR, new CLI surface; static tier): `cs
  init` writes `~/.<slug>-cs/.env` itself (getpass for the mailbox password,
  `FIREBASE_WEB_API_KEY` from the Step-0 descriptor, `CS_ACCOUNTS` from the
  accounts registry; never overwrites, EOF-safe, 0600) — gate 24; the README
  quick-start cut to size, install snippets resolving the newest tag
  dynamically (a literal `cs-kernel@vX.Y.Z` in README is now a gate
  failure); the wizard's clone-pin default follows the operational pin.
- Clone re-pin to `v0.8.x` is in progress (mrcall-cs first, static
  re-collaudo); the matrix below still shows the last signed state.
- The multi-provider LLM path (v0.4.0) is still **unwired**: no kernel call
  site passes `role=`, and `CS_LLM_ROUTE` defaults to the engine — it is
  behavior-neutral for a clone until one call site opts in.
- Measured recommendation for that path: `MODEL_CLASSIFIER=@glm` (A/B on the
  live classification task, 2026-07-28; full record in meta-repo
  `docs/briefs/2026-07-28-multi-provider-llm-ab.md` — quotes customer mail,
  never enters this repo).

## Unresolved

- **First wiring candidate** for the LLM path is whatever replaces `giada.py`
  (the batch-2 campaign loop is being superseded by a more general agent —
  the A/B measurement transfers to it). One `role=Role.CLASSIFIER` argument +
  `MODEL_CLASSIFIER=@glm` + `CS_LLM_ROUTE=direct` in the clone's env.
- **The A/B gold was adjudicated by the same party that built the harness**
  (disclosed in the brief §7.6). The safety metric and cost/latency numbers
  do not depend on it; the lenient-accuracy ranking does.
- The collaudo `live` gate is RED-by-default by construction (it diffs LLM
  prose and clock-dependent state such as `campaign_pending` vs `sms_hour`);
  the fix is filed in the meta-repo `docs/harness-backlog.md`.

## Next

1. Promote the batch-2 loop's reusable parts: the flock'd schedule store
   (`schedule.py`), the deterministic migrator pattern (`migrator.py`), and
   the IMAP attachment reader (`ext/attachments.py` — the engine indexes
   filenames but stores no bytes and exposes no fetch RPC). The attachment
   reader is the clearest candidate, since every clone's `/find-document`
   wants it.
