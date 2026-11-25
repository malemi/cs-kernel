---
status: active
created: 2026-11-06
---

# Desktop operator helpers on main

## Owned scope

The [brief](../briefs/2026-11-06-desktop-operator-main.md) and
[component contract](../desktop-operator-source.md) describe this kernel-owned
slice. REMOTE owns Desktop; shared working files and installed services remain
untouched. Base is `596a5c02bf7d5ef74c5e0ab58f5e145126704110`.
The ten-helper/five-test donor is `6445d1eb0e31a873c4c01f095dd7bac2298eef45`.

## Construction and actual checks

The bounded compatibility refinement is APPROVED. Exact deny insertions and
strict template successor enforcement are implemented; fresh source/integration review is APPROVED. Final publication closure remains
a separate gate. The source/test diff SHA256 is
`55823de043de1d49578c3297b7766a919148c4c841e01e6b72f34f7a61e3fbae`
after the reviewed local-only diagnostic correction. The previous diff and gate1
failure remain retained; actual STDIO/HTTP assertions and unchanged gate1 pass.

- The first actual main run remains exit1: 33 tests, 30 pass, one skip, one failure
  and one error. It identified the missing owner-method denies and the unselected
  legacy managed-aware workflow expectation. Original log and result are retained.
- The corrected selected run is exit0: 32 tests, 31 pass and one standalone skip.
  Only the reviewed newly donated workflow test is omitted; no main test is dropped.
- Gate63 passes with all 58 original main check ASTs and base03b4449 preserved.
  Whole source and four rendered variants per template are bound before/after.
  Four successor tests pass with 64 targeted negative mutations.
- Rebuilt wheel binds all ten helper modules and both permission resources;
  twenty imported `cs` module origins resolve to extracted candidate source.
  Dependencies come from explicit existing sites, not a fresh installation.

Exact private evidence is under `/tmp/kernel-mcp-main-20261106/`: the original
`focused.log`/`focused-result.json`, `compatibility-review.md`, and `execute/`
(`revision-report.md`, `candidate-manifest.json`, `candidate.diff`, `results.json`,
`preservation.json`, wheel and mutation-control logs) describe the predecessor.
The corrected candidate binds `execute/diagnostic-correction/candidate-manifest.json`,
`candidate.diff` and `revision-report.md` in that same correction directory;
`integration-recheck.md` is its actual approval. The 21-path selected candidate is
frozen there; all other 288 tracked main files were unchanged. Combined execution
against the M1–M3 RPC passes all five selected files (31 pass, one retained skip).

The combined frozen source commit is `67bf9ddc9c9549cf8287df0307f3c6e092e22e20`;
its `cs` tree is `39e749c5d54a80cc7ca1bf039cf9bb1fddc762b8`. It is available for
REMOTE-owned Git-ref paired builds, not installed adoption. The operator evidence
root `kernel-mcp-main-source` retains the original and corrected MCP packets;
`kernel-core-main-source/source-commit.json` binds the full combined package source.

## Publication and remaining obligations

Obtain fresh source/integration review, then combine only frozen reviewed paths
with the separately approved M1–M3 source candidate. Any shared dependency change
requires actual focused checks against the combined bytes. Reconcile documents,
run mechanical and semantic checks and fresh final publication review. Fetch main,
resolve/review true conflicts, and use normal main-only fast-forward publication.
Retain the exact commit and remote verification. Rollback is a reviewed normal
revert, not rewritten published history.

Current-main Desktop pairing, standalone SDK discovery, managed-native workflow
acceptance, operational adoption, provider/FULL and M4 remain unverified or
separately owned. Parent checker binding remains separate. This active trace
claims no baseline advancement, runtime acceptance, tag or release.
