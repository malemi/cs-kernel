# Release & upgrade procedure — and every place a version number lives

Why this file exists: on 2026-08-19 a single upgrade surfaced SEVEN stale
version claims across the kernel and the two clones (`v0.2.0`, `v0.3.0`,
`v0.5.1` ×3, a wizard default two releases behind, a README pin two releases
behind) plus a tag published without its release commit. Each one had been
"updated by hand at each release". Hand-updated version literals rot;
this file is the procedure that finds them all, every time.

**The rule: a version number may appear only where a procedure step OWNS
it.** Anything else is either derived (computed from the owner), historical
(append-only records, never edited), or a defect.

## The sweep — mandatory at every release AND every clone upgrade

Run in the kernel repo and in EVERY clone. Match ALL versions from `0.1.0`
up, not just the current one — the stale claim you are hunting is by
definition an old number:

```bash
grep -rInE '\bv?0\.[0-9]+\.[0-9]+\b' --exclude-dir=.git \
     --exclude-dir=.venv --exclude-dir=__pycache__ .
```

Classify every hit, no exceptions:
- **LIVE** — a claim about the present (a pin, a default, a stamped row, a
  marker line). Must agree with its owner below; fix it if it does not.
- **HISTORICAL** — CHANGELOG sections, `active-context-archive.md`, incident
  logs, `TAG_VERSION_EXCEPTIONS`, dated narrative. Never edited.
- **STRUCTURAL** — jinja templates (`{{ repo_kernel_version }}`), docstring
  examples, other products' versions (e.g. the mrcall-desktop app's
  `v0.1.29`). Leave alone.

The release or upgrade is done only when every LIVE hit agrees with its
owner. Not before.

## Version-claim inventory — kernel (this repo)

| Location | Owner step |
|---|---|
| `pyproject.toml` `version` | the release commit (the ONE hand-written number) |
| `CHANGELOG.md` "Current operational pin" marker | re-pin sign-off, after BOTH clones move |
| `CHANGELOG.md` `## vX.Y.Z` sections | append-only at release; never edited after |
| `docs/active-context.md` "Latest release tag / Current HEAD status" | release commit (tagged-as) + first post-tag commit (untagged) |
| `tests/test_release_consistency.py` `IMMUTABLE_TAG_TARGETS` | first post-tag commit pins the new tag's object |
| `tests/test_release_consistency.py` `TAG_VERSION_EXCEPTIONS` | operator decision only — records immutable mistakes |
| `README.md` install lines | NONE — literal pins are a gate failure; the snippet resolves the newest tag at run time |
| `cs/project_init.py` wizard pin default | NONE — derived from `kernel_version_bare()`; never a literal |

## Version-claim inventory — every clone

| Location | Owner step |
|---|---|
| `requirements.txt` pin | `cs update --pin <tag>` — **this is the truth; every other clone claim must agree with it** |
| `template-manifest.json` `init_data.repo_kernel_version` | bare number, no `v`. Today: fixed by hand at re-pin; a pending kernel change makes `cs update --pin` own it (active-context Next) |
| `manifest.toml` `[repo].kernel_version` | NONE — removed from the template in `v0.18.0`. Nothing parsed it and no gate checked it, so it was right only when somebody remembered. Delete the line from an existing clone at the next re-pin; `requirements.txt` is the pin |
| `requirements.lock` resolved commit | regenerate from the collaudo'd venv at every re-pin, and install it ALONE into a throwaway `uv venv` to prove it. Nothing enforces this: both clones' locks once resolved `v0.19.0`'s commit while `requirements.txt` said `v0.22.0`, so a venv rebuilt from the lock would have run a kernel three releases old |
| `docs/ARCHITECTURE.md` "Kernel pin" row | stamped clones: re-render; as-built clones (124-cs): edit the row at re-pin |
| `docs/active-context.md` pin claims (where present) | hand, at re-pin |

## Release (kernel) — in order

1. Everything to ship is committed; `bash tests/run.sh` green.
2. **Release commit**: bump `pyproject.toml`; write the `CHANGELOG.md`
   `## vX.Y.Z` section (why/what/migration/**Re-collaudo tier**, decided by
   what the release TOUCHES — see `CLAUDE.md`); `active-context.md` claims
   `Latest release tag` + `Current HEAD status: tagged as` the new tag.
3. `git tag vX.Y.Z` **immediately** (the gate is red in the gap).
4. `bash tests/run.sh` again — gates verified AT the tag.
5. First post-tag commit: `active-context.md` back to `untagged`; pin the
   tag's object in `IMMUTABLE_TAG_TARGETS`.
6. **Run the sweep** (above) on the kernel.
7. Push (main + tag) — operator's explicit ok. A published tag never moves;
   a tag published by mistake is recorded in `TAG_VERSION_EXCEPTIONS` and
   fixed forward, never deleted.

## Upgrade (each clone) — in order

1. **`cs update` — that is the whole upgrade** (since `v0.9.2`). It offers
   the newest tag (`Found new tag … Update? [y/N]`); on "y" it re-pins,
   runs `uv pip install`, re-execs on the new kernel and refreshes the
   templates. `cs --version` must then print the tag's number. Use
   `cs update --pin <tag>` + `uv pip install -r requirements.txt` ONLY for
   a specific version — above all a rollback; **never `pip install`**: a
   venv made per the README (`uv venv`) has no `pip` module in it.
   `cs update --check` looks and writes nothing.
2. The template refresh (step 1's tail, or a bare `cs update` when already
   current). Conflicted prose (`docs/`, `company/`): keep local for
   as-built files, `diff` when unsure. `settings.json` and the cron wrapper
   are applied regardless (local saved as `*.local-bak`) — diff them
   against the pre-update copy as static-collaudo evidence.
   `requirements.txt` and `manifest.toml` are clone-owned and never
   touched (`-v` reports them).
4. Align the clone inventory (table above): `template-manifest.json`
   init_data, `manifest.toml`, `ARCHITECTURE.md`, `active-context.md`.
5. **Run the sweep** on the clone. Fix every LIVE mismatch now.
6. `cs whoami` proof call; re-collaudo per the tag's CHANGELOG tier.
7. Commit by explicit path; after BOTH clones: update the CHANGELOG
   operational-pin marker in the kernel.
