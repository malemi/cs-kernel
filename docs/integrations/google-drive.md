# Google Drive

## What we can do

The integration lists, searches and reads files visible to the configured
service account. Use it to find a customer guide or internal runbook, read the
source text, and cite the actual document in a grounded response.

```bash
.venv/bin/python -m cs drive ls
.venv/bin/python -m cs drive ls FOLDER_OR_SHARED_DRIVE_ID
.venv/bin/python -m cs drive search "SIP trunk"
.venv/bin/python -m cs drive search "SIP trunk" "SHARED_DRIVE_NAME"
.venv/bin/python -m cs drive cat FILE_ID
```

`ls` discovers visible shared drives and individually shared files, or lists a
specified folder. `search` uses Drive full-text search, prints matching file IDs
and identifies the searched scope. `cat` extracts text. Google Docs, Sheets and
Slides use exports; the implementation also handles PDF, DOCX and XLSX text.

## Configuration and access

The integration uses the clone's `firebase_sa_path` key with the Drive read-only
scope. Enable Drive API on the service account's project and share the required
documents, folders or shared drives with its address. There is no domain-wide
delegation. The configured credentials determine which files can be reached.

`[drive].scope` selects the default shared drive for searches. An explicit name
or ID overrides it; `all` searches everything visible to the service account.
The default search scope is not an access restriction on `ls` or `cat`.
An absent or ambiguous search selector needs correction before searching.

## Limits and failure handling

- Access is read-only: no upload, editing, sharing, deletion or permission changes.
- Text extraction does not preserve the full visual layout. Do not assume an
  image, scanned page or formatting-dependent instruction was read correctly.
- PDF extraction requires `pdftotext`. Missing extraction support or a PDF with
  no extractable text produces a diagnostic marker; that is not document text.
  Other binary formats can yield unreadable output. Treat that as incomplete
  source evidence even when the command exits successfully.
- An empty folder listing can mean empty or inaccessible; the CLI reports both
  possibilities. An API failure is not proof that a document does not exist.
- Reading does not save a document into engine memory automatically. Durable
  knowledge storage is a separate authorized workflow with source provenance.

## Verification and implementation

[The Drive module](../../cs/drive.py) owns read-only authorization, paging,
exports, extractors and command dispatch. Three real Drive source documents
were read during the SIP procedure work on 2026-09-11. The 2026-09-13
documentation review checked source behavior and CLI wiring, not every file
format or every clone's sharing. Verify a new clone with `drive ls` and a known
shared document before relying on access.
