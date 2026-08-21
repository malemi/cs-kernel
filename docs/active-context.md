---
doc_baseline_commit: b888a56
doc_baseline_date: 2026-08-21
---

# Active Context — cs-kernel

Volatile state for the shared kernel of the `<company>-cs` operators. The
durable reference is [`CLAUDE.md`](../CLAUDE.md) (the anti-fork charter, layout,
release rules) and [`CHANGELOG.md`](../CHANGELOG.md) (what each tag changed and
which clones must re-collaudo). Pruned history lives in
[`active-context-archive.md`](active-context-archive.md). This file tracks only
what is *current*.

## State now

- **Latest release tag: `v0.9.6`. Current HEAD status: tagged as `v0.9.6`.** The
  `v0.9.x` train (2026-08-21) rebuilt the operator-facing surface; what each
  tag did is in `CHANGELOG.md`, not here. All static tier. `v0.8.0` remains
  the recorded tag→0.7.1 exception (object pinned immutable).
- The repo is **public** at `github.com/malemi/cs-kernel` — the single origin.
  The old private `hahnbanach/cs-kernel` is archived; the clone guide points
  at the public one.
- **The surface a clone now gets:** five `cs-`-prefixed commands —
  `/cs-review` (the ONE sit-down bootstrap: what the operator prepared, plus
  the day's outreach candidates where a producer is wired), `/cs-account`,
  `/cs-cron`, `/cs-campaign`, `/cs-help` — over the operator skills
  (`cs-operator`, `cs-triage-mail`, `cs-campaign-tick`, `cs-customer`,
  `cs-find-document`). `/munchausen` no longer exists.
- **Upgrading a clone is one command.** Bare `cs update` checks the pinned
  origin, offers any newer tag (`Found new tag … Update? [y/N]`, default No,
  EOF-safe), and on "y" re-pins → `uv pip install` → re-execs on the new
  kernel → re-stamps the templates. `--pin` is the specific-version/rollback
  hatch; `--check` looks and writes nothing. `requirements.txt` AND
  `manifest.toml` are clone-owned: `cs update` never touches either.
- Clone matrix (verified 2026-08-21 from inside each clone —
  `requirements.txt` + `cs --version`; measuring `python -m cs` from another
  cwd reads the local package, not the clone's):

  | Clone | Pinned / installed | Collaudo | Operator |
  |---|---|---|---|
  | `mrcall-cs` | `v0.9.4` | static | un-paused; cron deliberately not installed (interactive-only — operator decision 2026-08-19; `cs cron install` turns it on) |
  | `124-cs` | `v0.9.1` | static — 2026-08-21 (security files byte-identical, whoami OK) | un-paused, ticking (cron installed) |

- The kernel runs per-invocation from each clone's venv (no long-running
  kernel process). The provider side is the mrcall-desktop daemons, deployed
  at `d239e5f` (2026-08-03).
- Tagging procedure the release gate imposes: the release commit itself claims
  `Latest release tag:` + `Current HEAD status: tagged as` for the new
  vX.Y.Z, so the gate is red in the gap — commit, tag immediately, verify the
  gates AT the tag. The first post-tag commit flips the HEAD status back to
  untagged and pins the tag's commit id in `IMMUTABLE_TAG_TARGETS`
  (`tests/test_release_consistency.py`). Full procedure + the version-claim
  inventory: [`release-procedure.md`](release-procedure.md).
- The multi-provider LLM path is **partly live**. The `role=`/`CS_LLM_ROUTE`
  ROUTING seam is unwired: no kernel call site passes `role=`, and
  `CS_LLM_ROUTE` defaults to the engine. But the send guard's register
  judgment is a direct provider call — `cs/send_guard.py:337
  worker_llm.classify`, inside `judge_register`, reached from `evaluate`
  (`:374`) which `send_guard.check` wraps, and `cs/send_mail.py:162` runs
  that guard on the **model-composed** send path (`body_md`); a genuine
  fixed-template send passes an authored `plain`/`html` pair and never
  reaches it. The call is gated by `llm_available()` — anthropic SDK plus a
  resolved provider credential — NOT by `CS_LLM_ROUTE`, and degrades loudly
  to deterministic checks without one. **Measured per clone 2026-08-21**
  (`llm_available()`, run inside each): `mrcall-cs` → **True**
  (`OPENROUTER_API_KEY` present in `~/.mrcall-cs/.env`) — its register
  judgment is LIVE and already spending provider tokens on
  model-composed sends; `124-cs` → False, SDK absent. Do not infer this
  state from the packaging: reading the dependency list and concluding
  "no key configured" is how this file carried the wrong answer for a
  day. Run the check.
- Measured recommendation for that path: `MODEL_CLASSIFIER=@glm` (A/B on the
  live classification task, 2026-07-28; full record in meta-repo
  `docs/briefs/2026-07-28-multi-provider-llm-ab.md` — quotes customer mail,
  never enters this repo).

## Unresolved

- **`124-cs` sits at `v0.9.1`, four tags behind `mrcall-cs`.** Re-pinning the
  clones is the operator's own move (stated 2026-08-21, after a `cs update`
  overwrite cost him a hand-authored `manifest.toml` — since fixed, but the
  boundary stands). One `cs update` + "y" in that clone closes it.
- The `CHANGELOG.md` "Current operational pin" marker names one tag for both
  clones; the clones are currently split (`v0.9.4` / `v0.9.1`). The marker is
  written to reflect that until they converge.
- The `cs init` install offer and the secrets writer are gate-proven (gates
  24/25, function level) but the full **interactive `cs init` walk** on a
  fresh machine has never been run end to end. The clean-Mac customer walk
  (meta-repo Phase B handoff, open item 4) is the verification vehicle.
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

1. `cs update --pin <tag>` must also refresh `template-manifest.json`'s
   `init_data.repo_kernel_version` (bare number, no `v`). Found 2026-08-19:
   mrcall-cs's init_data still said `"v0.3.0"` five releases later, so the
   ARCHITECTURE re-stamp would have rendered `cs-kernel@vv0.3.0` — stamped
   data rots when the pin verb doesn't own it. Now that the upgrade offer
   re-pins on the operator's behalf, the verb owning that field matters more,
   not less.
2. Finish charter rule 6's vocabulary clean-up: `cs update --check` and the
   upgrade prompt still print `re-collaudo: <tier>` and "Every kernel
   upgrade owes a re-collaudo (CLAUDE.md, Versioning & release)"
   (`cs/project_update.py:252, 256, 304, 347`; README 404/407/439). The
   operator has already objected to exactly this vocabulary once. Replace
   with what a tier MEANS for them ("re-test before trusting it unattended")
   or drop it from their surface.
3. Promote the batch-2 loop's reusable parts: the flock'd schedule store
   (`schedule.py`), the deterministic migrator pattern (`migrator.py`), and
   the IMAP attachment reader (`ext/attachments.py` — the engine indexes
   filenames but stores no bytes and exposes no fetch RPC). The attachment
   reader is the clearest candidate, since every clone's `/cs-find-document`
   wants it.
