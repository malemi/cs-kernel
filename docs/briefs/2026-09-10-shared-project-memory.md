# Shared written project memory

<!-- doc-scope:start -->
Scope: product intent and acceptance criteria for moving company project memory
out of operator documentation and into the engine. The paired execution plan
owns implementation order; technical reference will own the final RPC contract.
<!-- doc-scope:end -->

## Problem and decision

Project dossiers, working status, meeting notes and attachments currently live
under each operator clone's `docs/projects/`. The kernel only scaffolds folders.
This mixes software documentation with business records and ties continuity to
one checkout. Both maintained companies already use this capability, satisfying
the kernel's rule of two. A metadata-only inventory found Markdown and binary
attachments in both; the largest existing file is below 340 KB. No dossier body
or session transcript was read for discovery.

Treat written projects as shared company memory owned by the engine. The kernel
owns the commands and agent procedures, never company records in its source repo.
Authored bytes and revision history remain distinct from extracted entity blobs.
They share the existing company membership boundary, not a search/LLM pipeline.

## User journey

An operator lists projects, opens the current status and only the needed files,
checks out a working copy when editing, and saves changes explicitly. Another
colleague using the same company memory can retrieve those saved documents from
another clone. Switching Claude Code/Codex does not require Git synchronization
of project records. Local working copies are conveniences, not the authority.

Existing directories can be imported with a preview followed by an explicit
commit. Import is additive, byte preserving and retryable, verifies stored hashes,
and never deletes source files. A differing existing document is a conflict,
not permission to replace it. A failed import reports incomplete progress and
is never called a completed migration. Old folders can remain as recovery copies;
new procedures address the engine and do not silently fall back to local copies.

## Acceptance criteria

1. Two owners in the same company read the same projects; different companies
   remain isolated. Unavailable memory fails clearly, never as an empty project.
2. Markdown, arbitrary binary attachments and relative directory structure round
   trip byte-for-byte, with explicit size/path refusals rather than skipped files.
3. Writes require an expected revision (zero means create only), record author
   and timestamp, and preserve immutable revisions. Identical retries converge;
   stale divergent edits fail without replacing newer work.
4. Listing is metadata-only and bounded. Reading loads a selected project/file,
   never all projects or session histories into an agent's startup context.
5. Import previews all proposed files, rejects symlinks/unsafe paths and excessive
   payloads before writing, preserves sources, and verifies each successful write.
   Checkout refuses unsafe or conflicting destinations; saving checks revision
   metadata, preserves local edits on failure and reports partial saves honestly.
6. Company-memory join cannot strand project data: preserve documents and history
   or refuse a divergent collision before changing membership. No silent dropping.
7. `cs project`, `cs memory`, the customer skill and stamped guidance agree on
   ownership and commands. Claude Code, Codex and OpenCode share the same updated
   skill bytes. No new project records are scaffolded under `docs/projects/`.
8. Stored payloads and company capabilities never appear in diagnostic logging.
   No LLM calls, outbound messages, or automatic blob extraction are involved.
9. Deterministic storage/transport/CLI migration and concurrency tests establish
   these outcomes, including recovery after interrupted import and stale save.

## Scope and limits

V1 supports shared written records, revision inspection, import and working-copy
round trips. It does not build a project-management UI, live collaborative editor,
background synchronization, search embeddings, access roles within a company,
file deletion or automatic blob summarization. Membership means existing shared
company-key access. Imported executable files are data and are never executed.

Keep existing operational clones running during development. New work uses
isolated source worktrees and temporary companies; deploy/migrate only after
independent acceptance review and the existing release gates. Source removal is
not part of this change. Backward compatibility is an actionable engine-upgrade
message, not a second local storage implementation.
