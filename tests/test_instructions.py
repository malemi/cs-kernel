#!/usr/bin/env python3
"""Semantic guard for `cs instructions` (`cs/instructions.py`).

Guards:
  (i)   compile_documents: absent company/ -> {}; a slot still carrying the
        stamped `## What to write here` heading compiles as absent, never a
        binding instruction nobody wrote — proven against TEXT THAT DIFFERS
        FROM TODAY'S TEMPLATE but still carries the heading (template drift
        must not un-mark an unedited slot), and the same text with the
        heading removed compiles as authored; a single non-empty file is
        returned byte-for-byte, reaching BOTH procedures.md and phone.md
        from the same playbook bytes; company/mailboxes/<email>.md reaches
        mail/<email>.md.
  (ii)  Two refusals, before any RPC: a collision (mailbox-identity.md and
        company/mailboxes/<own address>.md, case-insensitively, both landing
        on the same engine path), and a company/mailboxes/ file name that is
        not a mailbox address.
  (iii) diff_documents classifies against the engine truthfully: 'new' with
        nothing stored, 'unchanged' when the stored sha256 matches, 'changed
        (stored rev N)' otherwise.
  (iv)  cmd_instructions --commit calls ONLY instructions.store (never
        projects.write/projects.create) for the reserved project, verified
        against a fake RPC client that raises on any other method for that
        project's documents, and read-back-verifies every stored document.
  (v)   cs setup reports the stored-vs-compiled divergence by name.
"""
from __future__ import annotations

import base64
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cs import instructions as instructions_mod
from cs.project_documents import Documents, ProjectError, RESERVED_PROJECT_SLUG, digest
from cs.rpc import EngineError

MARKER = instructions_mod.STAMPED_MARKER


class FakeSettings:
    def __init__(self, email_address, state_dir):
        self.email_address = email_address
        self._state_dir = Path(state_dir)

    @property
    def state_dir(self):
        return self._state_dir


class FakeInstructionsEngine:
    """A minimal persistent revision model for the reserved project only —
    exercises client/verb behavior, not server correctness."""

    def __init__(self):
        self.space = "space-instructions"
        self.records: dict[str, list[bytes]] = {}
        self.calls: list[str] = []

    def _item(self, path, revision=None, content=False):
        revisions = self.records[path]
        revision = revision or len(revisions)
        data = revisions[revision - 1]
        result = dict(
            project=RESERVED_PROJECT_SLUG, path=path, revision=revision,
            sha256=digest(data), size=len(data), author_uid="owner-one",
            created_at="2026-09-30T12:00:00Z",
        )
        if content:
            result["content_base64"] = base64.b64encode(data).decode()
        return result

    def __call__(self, settings, method, params):
        self.calls.append(method)
        if method == "projects.list":
            return dict(space_id=self.space, items=[], total=0,
                        limit=params["limit"], offset=params["offset"])
        if method == "projects.read":
            if params.get("project") != RESERVED_PROJECT_SLUG:
                raise AssertionError("read outside the reserved project: %r" % params)
            path = params["path"]
            if path not in self.records:
                raise EngineError(-32044, "missing")
            return dict(space_id=self.space, **self._item(path, params.get("revision"), True))
        if method == "instructions.store":
            path = params["path"]
            data = base64.b64decode(params["content_base64"])
            revisions = self.records.setdefault(path, [])
            expected = params["expected_revision"]
            if expected != len(revisions):
                raise EngineError(-32040, "conflict")
            if not revisions or revisions[-1] != data:
                revisions.append(data)
            return dict(space_id=self.space, **self._item(path))
        # Anything else — in particular projects.write / projects.create —
        # must never be reached for this project. The verb has one door.
        raise AssertionError(
            "unexpected RPC method against the reserved standing-instructions "
            "project: %s %r" % (method, params)
        )


class CompileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.settings = FakeSettings("Support@Acme.example", self.root / "state")

    def test_absent_company_dir(self):
        self.assertEqual(instructions_mod.compile_documents(self.root, self.settings), {})
        self.assertEqual(
            instructions_mod.absent_slots(self.root, self.settings),
            [instructions_mod.PLAYBOOK_FILE, instructions_mod.IDENTITY_FILE],
        )

    def test_marker_present_compiles_as_absent_even_after_template_drift(self):
        """The untouched marker survives a future reword of the slot's
        instructions — text that differs from whatever the CURRENT template
        says, but still carries the heading, must still compile as absent.
        A re-render-based check would get this wrong (module docstring)."""
        drifted = (
            "# A totally reworded heading no template ever shipped\n\n"
            + MARKER + "\n\nSome future instructions that do not exist today.\n"
        )
        path = self.root / instructions_mod.PLAYBOOK_FILE
        path.parent.mkdir(parents=True)
        path.write_text(drifted)
        self.assertEqual(instructions_mod.compile_documents(self.root, self.settings), {})
        self.assertIn(
            instructions_mod.PLAYBOOK_FILE,
            instructions_mod.absent_slots(self.root, self.settings),
        )

    def test_marker_removed_from_same_drifted_text_is_authored(self):
        """The SAME drifted text, with only the marker heading deleted (the
        documented signal, company/README.md.j2), compiles as authored."""
        drifted_without_marker = (
            "# A totally reworded heading no template ever shipped\n\n"
            "Some future instructions that do not exist today.\n"
        )
        path = self.root / instructions_mod.PLAYBOOK_FILE
        path.parent.mkdir(parents=True)
        path.write_text(drifted_without_marker)
        docs = instructions_mod.compile_documents(self.root, self.settings)
        self.assertEqual(docs[instructions_mod.PROCEDURES_PATH], drifted_without_marker.encode())
        self.assertEqual(docs[instructions_mod.PHONE_PATH], drifted_without_marker.encode())

    def test_non_utf8_content_is_authored_not_silently_dropped(self):
        """No template render happens during compile any more — a slot's own
        bytes are the only input the marker check reads, and un-decodable
        bytes (the marker literally cannot be "found" in them) must still
        compile as authored, never silently disappear."""
        path = self.root / instructions_mod.PLAYBOOK_FILE
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\xff\xfe not valid utf-8, but real content\n")
        docs = instructions_mod.compile_documents(self.root, self.settings)
        self.assertEqual(docs[instructions_mod.PROCEDURES_PATH], path.read_bytes())

    def test_empty_authored_file_compiles_as_absent(self):
        path = self.root / instructions_mod.PLAYBOOK_FILE
        path.parent.mkdir(parents=True)
        path.write_text("")
        self.assertEqual(instructions_mod.compile_documents(self.root, self.settings), {})

    def test_single_file_byte_equal_reaches_procedures_and_phone(self):
        playbook = b"Refunds: check the order id, then issue one within policy.\n"
        path = self.root / instructions_mod.PLAYBOOK_FILE
        path.parent.mkdir(parents=True)
        path.write_bytes(playbook)

        docs = instructions_mod.compile_documents(self.root, self.settings)
        self.assertEqual(docs[instructions_mod.PROCEDURES_PATH], playbook)
        self.assertEqual(docs[instructions_mod.PHONE_PATH], playbook)
        self.assertNotIn(instructions_mod.mailbox_path(self.settings.email_address), docs)

    def test_identity_file_reaches_own_mailbox_lowercased(self):
        identity = b"Sign as Support. Formal register. English only.\n"
        (self.root / instructions_mod.IDENTITY_FILE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / instructions_mod.IDENTITY_FILE).write_bytes(identity)

        docs = instructions_mod.compile_documents(self.root, self.settings)
        self.assertEqual(
            docs[instructions_mod.mailbox_path("support@acme.example")], identity
        )
        self.assertEqual(list(docs), ["mail/support@acme.example.md"])

    def test_mailboxes_dir_reaches_per_address_identity(self):
        mailboxes = self.root / instructions_mod.MAILBOXES_DIR
        mailboxes.mkdir(parents=True)
        (mailboxes / "riccardo@acme.example.md").write_bytes(b"Sign as Riccardo.\n")
        (mailboxes / "empty@acme.example.md").write_bytes(b"")

        docs = instructions_mod.compile_documents(self.root, self.settings)
        self.assertEqual(
            docs["mail/riccardo@acme.example.md"], b"Sign as Riccardo.\n"
        )
        self.assertNotIn("mail/empty@acme.example.md", docs)
        self.assertIn(
            "%s/empty@acme.example.md" % instructions_mod.MAILBOXES_DIR,
            instructions_mod.absent_slots(self.root, self.settings),
        )

    def test_collision_identity_file_vs_own_address_in_mailboxes_dir(self):
        """`company/mailbox-identity.md` and `company/mailboxes/<own
        address>.md` — matched case-INsensitively, per the engine's own
        `strip().lower()` path mapping — both compile to the same engine
        path. Refused before any RPC, naming both files."""
        (self.root / instructions_mod.IDENTITY_FILE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / instructions_mod.IDENTITY_FILE).write_bytes(b"Sign as OLD.\n")
        mailboxes = self.root / instructions_mod.MAILBOXES_DIR
        mailboxes.mkdir(parents=True)
        # Different case than settings.email_address ("Support@Acme.example")
        # on purpose — the collision must be caught regardless of case.
        (mailboxes / "SUPPORT@ACME.EXAMPLE.md").write_bytes(b"Sign as NEW.\n")

        with self.assertRaises(ProjectError) as ctx:
            instructions_mod.compile_documents(self.root, self.settings)
        message = str(ctx.exception)
        self.assertIn(instructions_mod.IDENTITY_FILE, message)
        self.assertIn("mailboxes/SUPPORT@ACME.EXAMPLE.md", message)

    def test_malformed_mailboxes_filename_refused(self):
        """A `company/mailboxes/` file name that is not a mailbox address —
        e.g. a stray README — is refused before any RPC, naming the file."""
        mailboxes = self.root / instructions_mod.MAILBOXES_DIR
        mailboxes.mkdir(parents=True)
        (mailboxes / "README.md").write_bytes(b"notes\n")

        with self.assertRaises(ProjectError) as ctx:
            instructions_mod.compile_documents(self.root, self.settings)
        self.assertIn("mailboxes/README.md", str(ctx.exception))


class DiffTests(unittest.TestCase):
    def setUp(self):
        self.engine = FakeInstructionsEngine()

    def client(self):
        return Documents(None, self.engine)

    def test_new_unchanged_changed(self):
        client = self.client()
        client.page("list", limit=1)
        docs = {"procedures.md": b"v1\n"}
        rows = instructions_mod.diff_documents(client, docs)
        self.assertEqual(rows, [("procedures.md", "new", digest(b"v1\n"), None)])

        self.engine.records["procedures.md"] = [b"v1\n"]
        rows = instructions_mod.diff_documents(client, docs)
        self.assertEqual(rows, [("procedures.md", "unchanged", digest(b"v1\n"), 1)])

        docs2 = {"procedures.md": b"v2\n"}
        rows = instructions_mod.diff_documents(client, docs2)
        self.assertEqual(
            rows, [("procedures.md", "changed (stored rev 1)", digest(b"v2\n"), 1)]
        )


class CommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "manifest.toml").write_text("")
        self.settings = FakeSettings("support@acme.example", self.root / "state")
        playbook = self.root / instructions_mod.PLAYBOOK_FILE
        playbook.parent.mkdir(parents=True)
        playbook.write_bytes(b"Refunds: verify, then issue.\n")
        self.engine = FakeInstructionsEngine()

    def test_commit_stores_via_instructions_store_only_and_verifies_readback(self):
        client = Documents(self.settings, self.engine)
        client.page("list", limit=1)
        docs = instructions_mod.compile_documents(self.root, self.settings)
        rows = instructions_mod.diff_documents(client, docs)
        for path, _status, _checksum, revision in rows:
            stored = instructions_mod._store(client, path, docs[path], revision or 0)
            _verified, readback = client.read(RESERVED_PROJECT_SLUG, path, stored["revision"])
            self.assertEqual(readback, docs[path])

        self.assertIn("instructions.store", self.engine.calls)
        self.assertNotIn("projects.write", self.engine.calls)
        self.assertNotIn("projects.create", self.engine.calls)
        self.assertEqual(
            self.engine.records[instructions_mod.PROCEDURES_PATH][-1], docs["procedures.md"]
        )
        self.assertEqual(
            self.engine.records[instructions_mod.PHONE_PATH][-1], docs["phone.md"]
        )

    def test_nonempty_retirement_replaces_prior_playbook_and_identity(self):
        client = Documents(self.settings, self.engine)
        client.page("list", limit=1)
        identity = self.root / instructions_mod.IDENTITY_FILE
        identity.write_bytes(b"Sign every response as Example Agent.\n")
        prior = instructions_mod.compile_documents(self.root, self.settings)
        for path, data in prior.items():
            instructions_mod._store(client, path, data, 0)
        (self.root / instructions_mod.PLAYBOOK_FILE).write_bytes(
            b"No standing refund-response procedure remains.\n")
        identity.write_bytes(b"No standing signature rule remains.\n")
        replacement = instructions_mod.compile_documents(self.root, self.settings)
        self.assertEqual(set(replacement),
                         {"procedures.md", "phone.md", "mail/support@acme.example.md"})
        for path, _status, _checksum, revision in instructions_mod.diff_documents(client, replacement):
            self.assertEqual(revision, 1)
            stored = instructions_mod._store(client, path, replacement[path], revision)
            self.assertEqual(stored["revision"], 2)
            verified, data = client.read(RESERVED_PROJECT_SLUG, path, 2)
            self.assertEqual(data, replacement[path])
            self.assertNotEqual(data, prior[path])
            self.assertNotIn(b"Refunds: verify, then issue.", data)
            self.assertNotIn(b"Sign every response as Example Agent.", data)
            self.assertEqual(verified["sha256"], digest(replacement[path]))
        self.assertTrue(all(row[1] == "unchanged" for row in
                            instructions_mod.diff_documents(client, replacement)))

    def test_absent_input_does_not_retire_prior_published_rule(self):
        client = Documents(self.settings, self.engine)
        client.page("list", limit=1)
        prior = instructions_mod.compile_documents(self.root, self.settings)
        for path, data in prior.items():
            instructions_mod._store(client, path, data, 0)
        (self.root / instructions_mod.PLAYBOOK_FILE).write_bytes(b"")
        self.assertEqual(instructions_mod.compile_documents(self.root, self.settings), {})
        for path, data in prior.items():
            self.assertEqual(client.read(RESERVED_PROJECT_SLUG, path)[1], data)

    def test_cmd_instructions_commit_end_to_end(self):
        import os
        from unittest.mock import patch

        class Args:
            commit = True
            verbose = True

        bound_documents = lambda settings, call=None: Documents(settings, call or self.engine)

        old_cwd = os.getcwd()
        os.chdir(self.root)
        try:
            with patch("cs.instructions.config.load", return_value=self.settings), \
                 patch("cs.instructions.Documents", bound_documents):
                out = io.StringIO()
                with redirect_stdout(out):
                    rc = instructions_mod.cmd_instructions(Args())
        finally:
            os.chdir(old_cwd)

        self.assertEqual(rc, 0)
        self.assertIn("stored revision", out.getvalue())
        self.assertNotIn("projects.write", self.engine.calls)
        self.assertNotIn("projects.create", self.engine.calls)
        # The local dry-run cache lands under the clone's own state dir.
        cached = self.settings.state_dir / "instructions" / "procedures.md"
        self.assertTrue(cached.is_file())
        self.assertEqual(cached.read_bytes(), b"Refunds: verify, then issue.\n")


class ReservedSlugRefusalTests(unittest.TestCase):
    def test_project_new_refuses_reserved_slug(self):
        from cs import project_memory

        class Args:
            name = RESERVED_PROJECT_SLUG
            title = None

        with self.assertRaises(ProjectError):
            project_memory._new(client=None, settings=None, args=Args())

    def test_project_save_refuses_reserved_slug(self):
        from cs.project_working import save
        import cs.project_working as pw

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".cs-project.json").write_text(json.dumps({
                "version": 1, "space_id": "sp", "project": RESERVED_PROJECT_SLUG,
                "files": {},
            }))
            with self.assertRaises(ProjectError):
                save(client=None, directory=str(root))

    def test_project_import_refuses_reserved_slug(self):
        from cs.project_working import import_projects

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "somefile.md").write_text("hello\n")
            with self.assertRaises(ProjectError):
                import_projects(client=None, directory=str(root), name=RESERVED_PROJECT_SLUG)


class SetupDivergenceSettings:
    """The subset of `Settings` `cs.setup.build` reads."""

    email_address = "support@acme.example"
    email_password = "app-password"
    imap_host = "imap.example.com"
    smtp_host = "smtp.example.com"
    engine_owner_uid = "uid-setup"
    engine_ws_url = "wss://engines.example.com"
    firebase_web_api_key = "public-key"

    @property
    def state_dir(self):
        return Path(tempfile.gettempdir()) / "cs-setup-divergence-test"


def _setup_call(engine):
    def call(settings, method, params=None, timeout=None, id_token=None):
        if method == "account.who_am_i":
            return {"signed_in": True, "uid": settings.engine_owner_uid}
        if method == "setup.state":
            return {"emails_count": 1, "emails_analyzed_count": 1, "emails_pending_analysis": 0,
                    "agents_trained": ["memory_message", "task_email", "emailer"]}
        if method == "memory.status":
            return {"has_key": True, "available": True}
        return engine(settings, method, params or {})
    return call


class SetupDivergenceTests(unittest.TestCase):
    def test_setup_reports_instructions_divergence_by_name(self):
        from cs import setup as setup_mod

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "manifest.toml").write_text("")
            (root / "AGENTS.md").write_text("charter\n")
            playbook = root / instructions_mod.PLAYBOOK_FILE
            playbook.parent.mkdir(parents=True)
            playbook.write_bytes(b"Refunds: verify, then issue.\n")

            engine = FakeInstructionsEngine()
            settings = SetupDivergenceSettings()
            report = setup_mod.build(
                settings, root=root, call=_setup_call(engine), which=lambda _: "/fixture/agent"
            )
            row = next(r for r in report["checks"] if r["id"] == "instructions")
            self.assertEqual(row["state"], "incomplete")
            self.assertIn("procedures.md", row["message"])
            self.assertIn("new", row["message"])
            self.assertIn("cs instructions --commit", row["action"])

            # Store the exact compiled bytes; the SAME check now reports clean.
            docs = instructions_mod.compile_documents(root, settings)
            client = Documents(settings, engine)
            client.page("list", limit=1)
            for path, data in docs.items():
                instructions_mod._store(client, path, data, 0)
            report = setup_mod.build(
                settings, root=root, call=_setup_call(engine), which=lambda _: "/fixture/agent"
            )
            row = next(r for r in report["checks"] if r["id"] == "instructions")
            self.assertEqual(row["state"], "ready")


if __name__ == "__main__":
    unittest.main(verbosity=2)
