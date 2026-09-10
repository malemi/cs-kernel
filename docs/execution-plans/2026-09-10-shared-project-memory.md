---
status: active
---
# Shared written project memory — execution plan

<!-- doc-scope:start -->
Scope: milestones, wire contract, verification and migration controls for the
paired shared-project-memory brief. It records implementation evidence, not
company project contents.
<!-- doc-scope:end -->

## Decision and review

Brief approved by an independent reviewer on 2026-09-10. Implement shared
engine storage and kernel access in isolated `feat/shared-project-memory`
worktrees. Keep company documents out of both source repositories. New storage
is additive and revisions immutable; no removal of operational source folders.

## Fixed V1 contract

Dedicated project-document, revision and space-identity tables live in the
existing company memory SQLite store. Include their table names in the memory
binding inventory; initialize an opaque random `space_id` under schema migration
ownership. Never expose the company capability. Resolve the currently bound
memory store for every operation. Authors are UID provenance, not visibility.

Every successful response includes `space_id`. A write/create requires the
expected `space_id`; mismatch fails before writing. This also binds working copies
to a company across account changes and memory joins. Document key is
(project slug, relative path), revision is an increasing positive integer;
expected revision zero means create only. Store raw bytes, SHA-256, timestamp
and author. Identical retries do not add revisions. Divergent stale writes fail.

RPC methods (all deterministic, no LLM or sending):

- `projects.list(limit?, offset?)`: metadata-only project summaries.
- `projects.files(project, limit?, offset?)`: current document metadata.
- `projects.read(project, path, revision?)`: one revision, base64 content + hash.
- `projects.write(space_id, project, path, content_base64, expected_revision)`:
  compare-and-swap one document, returning its current metadata.
- `projects.history(project, path, limit?, offset?)`: revision metadata only.
- `projects.create(space_id, project, files)`: atomically create the small initial
  scaffold; files are path/base64 pairs, and an existing project is refused.

Lists return `{space_id, items, total, limit, offset}`; document metadata has
`project`, `path`, `revision`, `sha256`, `size`, `author_uid`, `created_at`.
Read adds `content_base64`; write returns this metadata without content. Create
returns `{space_id, project, files: [metadata]}`. Bound pages to 100 (default50),
files to 4 MiB raw, scaffold to 16 files / 1 MiB raw aggregate, paths to 512 UTF-8
bytes and slugs to 100 ASCII chars. Base64 expansion stays below the existing
16 MiB WebSocket request limit. Strictly reject traversal, absolute/Windows paths,
symlinks and invalid payloads. No document contents in RPC logs or error strings.
Standard JSON-RPC validation errors map invalid input; domain conflicts/not-found/
unavailable memory use explicit stable application error codes and concise text.

Memory join copies documents and all revisions in the destination transaction.
Preflight divergent collisions before copying blobs or changing membership;
identical compatible histories converge, divergent history refuses with a useful
conflict. Mixed old stores without the tables act as empty source only. Destination
keeps its space_id; old working copies require explicit new checkout after join.

## M1 — engine storage and RPC

Implement models/binding/schema preparation, storage service, CAS, pagination,
scaffold transaction, read/history, payload redaction and handler registration.
Integrate lossless/refusing join into its existing transaction before membership
persistence. Validate actual dispatch and per-table binding, owner isolation,
concurrent writes, history, binary round trips, unavailable store, parameter
contracts, joined/changed space and secret-free logging. Independent integration
review must pass before downstream final integration.

## M2 — kernel workflow and migration

Keep `cs project new <slug> [--title]`, now creating the engine scaffold. Add:
`list`, `files <slug>`, `show <slug> [path]` (status.md default),
`history <slug> <path>`, `checkout <slug> <directory>`, `save <directory>`, and
`import <directory> [--name SLUG | --all] [--commit]`.

`show` can select an old revision, emit JSON or write byte-exact output to a new
file; binary is never decoded silently. Checkout creates a new directory and
private local `.cs-project.json` binding space, slug, base revisions and hashes;
refuse existing destinations and unsafe ancestors. Save previews changed/new
files and requires `--commit`; deletion is unsupported and reported, never
propagated. Preflight all candidate files/revisions before any write, then CAS each
file and verify read-back. On partial failure retain edits and accurately update
only successful metadata so retry is safe. Never automatically switch a stale
working copy to another company or fetch over local edits.

Import single project or all immediate project directories is a dry-run by
default. Scan/preflight the complete chosen tree before the first mutation;
report metadata only, conflict with existing different bytes, accept identical
files on retry, verify read-back hashes, and never delete originals. Explicitly
report excluded generated caches (`__pycache__`, `.pyc`, `.DS_Store`, `.git`);
reject sensitive `.env` paths rather than uploading them. Refuse symlinks and
unsupported/oversize files rather than silently omitting business attachments.
Top-level legacy README/templates are conventions, not a project to upload.
Bound each working-copy/import operation to 10,000 files and 128 MiB aggregate,
with explicit refusal rather than unbounded allocation.

Retire new `docs/projects/` scaffolding. Update canonical customer skill,
project conventions, project templates, memory report and relevant README/charter
references. Projects are authored evidence: compare date/provenance with blobs,
not automatic precedence by storage location. Load status first, then only needed
project documents. Blob writes remain a separate explicit procedure. Leave old
local directories as recovery data and identify their import path on old-engine
or missing-project errors; never use them as a silent live fallback.

## M3 — cross-repository acceptance and documentation

Exercise the actual kernel CLI over a controlled local WebSocket into the real
engine RPC/store using temporary companies and installed packages. Create, list,
selective read, checkout/edit/save, binary import/export, interrupted retry,
revision recovery, same-company second-owner read and wrong-space/conflict refusal.
No real company data needed. Prove original fixtures unchanged. Render all three
agent surfaces and check common bytes and correct host invocation guidance.

Run appropriate engine storage/memory/RPC suites and the full kernel gates;
update old scaffold and memory-map tests to the deliberately changed public
behavior rather than weakening assertions. Independent fresh final review covers
the user path, boundaries and documentation. Keep living docs current and run
mechanical plus semantic documentation checks. Record exact evidence and limits.

## Rollout and recovery

Do not deploy an unreviewed change into the user's active work. After acceptance,
follow existing engine/kernel release procedures; new CLI/storage surface is a
kernel MINOR. The changed customer workflow and company-join boundary require
FULL verification on both operational clones before publishing a kernel tag.
Preserve current credentials, custom deny rules, cron and unrelated edits.
Production import is additive and verified; originals remain available for
rollback. Existing binaries ignore new tables. No cleanup or background sync is
part of this rollout. If release cannot finish, state source-only availability
and the exact remaining step, never claim the production records moved.

## Progress

- Brief: approved.
- Plan: independently approved. Implementation started in isolated worktrees.
