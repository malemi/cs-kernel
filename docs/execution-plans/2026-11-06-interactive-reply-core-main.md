---
status: active
created: 2026-11-06
---

# M1–M3 main-source integration

## Scope and ownership

Follow the [bounded brief](../briefs/2026-11-06-interactive-reply-core-main.md)
and [source contract](../interactive-reply-source.md). Kernel lead owns the
throwaway current-main candidate; REMOTE owns Desktop. No shared-tree copying,
operational adoption or provider spending is part of this gate.

## Approved framing and source evidence

The dependency proposal SHA256 is
`a628c85d79bb562f5987315c349a148f4ce54b48e69fe08d508bdfd0d84623a2`.
Its prerequisite-binding manifest is
`efad783dcb2ddd407ab93c71233a1929756e0ffe3d8161ef6e78a0a6c57c71cd`.
Private evidence roots are `kernel-dependency-closure` and
`kernel-prerequisite-binding` under the operator's 2026-11-06 evidence directory.
The earlier M1–M5 product approvals remain valid for their exact frozen source;
this integration required fresh review of the new main bindings.

- Prerequisite review rejected a projection that lost peer conflict/incomplete
  authority. The corrected operator-only projection preserves those holds and
  leaves ordinary projection behavior unchanged.
- Fresh integrated source/test review is APPROVED. The exact source/test diff
  SHA256 is `a7b8a6f533de5716f3c3b84d21c82cfed0d3e30e747ea02c20cc40e42418ab2b`.
  That predecessor had thirty-one changed and 282 unchanged file hashes checked.
  A subsequent real ordinary-retirement check exposed the preserved main pairing
  signature mismatch; its explicit adapter correction is independently APPROVED.
  Lifecycle SHA256: `a708b06be6e004b018cc4d2ed6d1c4f8c260667ef71979fd4620087130117cc7`.
  The new ordinary-retirement script preserves five donor tests and adds context
  controls. Real CLI preview/commit invokes the actual lifecycle, proving no-effect
  preview and MOVE before engine discard; sent-mirror checks also pass.
- Seven selected scripts pass 70 tests; contextual-email passes 10; main
  draft-send/reply, actual CLI help, projection and integration controls pass.
  These are focused checks, not a new complete-suite result.
- This M1–M3 slice leaves main runner, gate63 and bootstrap guard unchanged.
  The separately reviewed MCP slice owns its exact permission successors. Three diagnostic
  prerequisites were source-reviewed; this does not import M4's collector chain.
- Original preparation/fixture/assertion failures and donor bytes remain retained.
  Adapted scheduled tests exercise main's actual guards and second-guard refusal;
  the unselected future scheduled publication assertion is explicitly excluded.

Exact private receipts: `/tmp/interactive-reply-core-main-20261106/execute/`
(`candidate-manifest.json`, `candidate.diff`, `revision-provenance.json`,
`mime-fixture-provenance.json`, `attempt3/`, `attempt4/`) and
`/tmp/mrcall-ai-kit/core-prerequisite-review/integration-recheck.md`.
These paths locate retained operational evidence, not packaged dependencies.

The frozen source commit is `67bf9ddc9c9549cf8287df0307f3c6e092e22e20`.
It includes the separately reviewed MCP slice; complete source/resource/metadata
bindings and raw review references are retained in
`kernel-core-main-source/source-commit.json` under the operator's 2026-11-06
evidence root. The ordinary-retirement correction and first CLI fixture failure
remain in `retirement-correction/`; `retirement-integration-recheck.md` supplies
its actual approval. The new source check supersedes the old mocked-dispatch
smoke for ordinary lifecycle availability, without rewriting that evidence.

## Source-publication procedure

1. Reconcile affected docs; mechanical check and independent doc-critic.
2. Fresh final source-publication review of exact candidate and limits.
3. Fetch remote main; review any true integration conflict. Commit only reviewed
   paths and normal fast-forward push to main; verify exact remote SHA.
4. Preserve a durable candidate/receipt manifest. A rollback after publication
   is a reviewed normal revert, never a history rewrite.

## Unmet parent obligations

The [M4 logs/collector integration](2026-11-06-interactive-reply-m4-main.md)
owns its separately reviewed prerequisite closure. M5 workflow source integration has its own
[bounded continuation](2026-11-06-interactive-reply-m5-main.md). The frozen
MCP ten-helper/five-test donor is a separate kernel-owned compatibility scope,
not blocked by M4 and not proof of Desktop current-main pairing. M6, native/provider
acceptance and both ordinary FULL clone obligations remain open. Controlled
recipient identity, spending limits and per-operation effect authority are not
invented by source approval. Parent completion-checker binding remains separately
owned; no parent completion or baseline advancement is claimed here.
