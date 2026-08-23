#!/usr/bin/env python3
"""`delete_draft()` removes ONE named draft, or refuses — it never guesses.

Why this gate exists (2026-08-23): the engine composed a reply that quoted a
sentence the customer had never written. The operator wrote a clean draft but
could not remove the bad one — nothing in cs could delete a draft — so a
fabricated quote sat in Gmail Drafts where a human could send it by mistake.
The fix deletes a person's mail, so every guard on it is asserted here:

  1. dry-run (the default) writes NOTHING and selects the folder read-only;
  2. zero matches → refuse, never "delete the first thing you find";
  3. more than one match → refuse, and report what matched;
  4. no \\Drafts special-use folder → refuse before selecting anything;
  5. a message not flagged \\Draft → refuse (the folder is not what it claims);
  6. a uid/Message-ID mismatch → refuse (the header search narrows, never widens);
  7. commit → exactly one UID MOVE, of the identified uid, into \\Trash — and
     never \\Deleted / EXPUNGE, which cannot be undone;
  8. no \\Trash folder → refuse rather than fall back to the expunge;
  9. the CLI verb exits non-zero on a refusal, and `--account` REFUSES it: the
     verb writes the operator's own Gmail, which the flag cannot redirect.

Hermetic: a fake IMAP object records every command. No mailbox, no network.
"""
from __future__ import annotations

import types

from cs import cli, config as cfg, gmail_drafts


BAD = {"uid": "41", "flags": r"41 (FLAGS (\Draft \Seen)", "to": "cliente@example.test",
       "subject": "Re: Domanda", "date": "Fri, 22 Aug 2026 18:00:00 +0200",
       "message_id": "<bad@example.test>"}
GOOD = {"uid": "42", "flags": r"42 (FLAGS (\Draft)", "to": "cliente@example.test",
        "subject": "Re: Domanda", "date": "Sat, 23 Aug 2026 09:00:00 +0200",
        "message_id": "<good@example.test>"}


class FakeIMAP:
    """Enough IMAP to drive delete_draft, and a log of every command issued."""

    def __init__(self, drafts, *, drafts_folder="[Gmail]/Bozze", trash="[Gmail]/Cestino"):
        self.drafts = {d["uid"]: d for d in drafts}
        self.drafts_folder = drafts_folder
        self.trash = trash
        self.commands: list[tuple] = []
        self.selected: tuple | None = None

    # --- transport ---------------------------------------------------------
    def list(self):
        self.commands.append(("LIST",))
        lines = [b'(\\HasNoChildren \\All) "/" "[Gmail]/Tutti"']
        if self.drafts_folder:
            lines.append(f'(\\HasNoChildren \\Drafts) "/" "{self.drafts_folder}"'.encode())
        if self.trash:
            lines.append(f'(\\HasNoChildren \\Trash) "/" "{self.trash}"'.encode())
        return "OK", lines

    def select(self, mailbox, readonly=False):
        self.commands.append(("SELECT", mailbox, readonly))
        self.selected = (mailbox, readonly)
        return "OK", [b"1"]

    def uid(self, command, *args):
        self.commands.append(("UID", command, *args))
        if command == "SEARCH":
            return "OK", [b" ".join(u.encode() for u in self._search(args))]
        if command == "FETCH":
            return "OK", self._fetch(args[0])
        if command == "MOVE":
            uid = args[0] if isinstance(args[0], str) else args[0].decode()
            assert self.selected and self.selected[1] is False, \
                "MOVE issued on a READ-ONLY selection"
            self.drafts.pop(uid, None)
            return "OK", [b"[COPYUID 1 42 7] (Success)"]
        raise AssertionError(f"unexpected UID command: {command} {args}")

    def logout(self):
        self.commands.append(("LOGOUT",))
        return "BYE", [b""]

    # --- the tiny bit of IMAP semantics the code depends on ----------------
    def _search(self, args):
        # args = (None, "UID", "42") | (None, "HEADER", "Message-ID", '"<x>"')
        keys = [a for a in args if a is not None]
        if keys[0] == "ALL":
            return sorted(self.drafts)
        if keys[0] == "UID":
            return [keys[1]] if keys[1] in self.drafts else []
        if keys[0] == "HEADER" and keys[1] == "Message-ID":
            want = keys[2].strip('"')
            return [u for u, d in sorted(self.drafts.items())
                    if want.lower() in (d["message_id"] or "").lower()]
        raise AssertionError(f"unexpected SEARCH: {args}")

    def _fetch(self, uid):
        uid = uid if isinstance(uid, str) else uid.decode()
        d = self.drafts.get(uid)
        if not d:
            return []
        hdr = (f"To: {d['to']}\r\nSubject: {d['subject']}\r\n"
               f"Date: {d['date']}\r\nMessage-ID: {d['message_id']}\r\n\r\n").encode()
        return [(d["flags"].encode() + b" BODY[HEADER.FIELDS (...)] {%d}" % len(hdr), hdr), b")"]


_REAL_DELETE = gmail_drafts.delete_draft  # the CLI tests stub it; they restore this


def _wire(fake) -> types.SimpleNamespace:
    gmail_drafts._imap = lambda settings: fake
    return types.SimpleNamespace()  # settings: unused once _imap is stubbed


def _no_writes(fake) -> None:
    verbs = [c[1] for c in fake.commands if c[0] == "UID"]
    assert "MOVE" not in verbs, fake.commands
    assert "STORE" not in verbs, fake.commands
    assert "EXPUNGE" not in verbs, fake.commands
    assert not any(c[0] == "EXPUNGE" for c in fake.commands), fake.commands


def test_dry_run_touches_nothing() -> None:
    fake = FakeIMAP([BAD, GOOD])
    out = gmail_drafts.delete_draft(_wire(fake), uid="41")

    assert out["ok"] is True and out["dry_run"] is True, out
    assert out["folder"] == "[Gmail]/Bozze", out           # resolved by \Drafts flag
    assert out["would_move_to"] == "[Gmail]/Cestino", out  # resolved by \Trash flag
    t = out["target"]
    assert (t["uid"], t["to"], t["subject"], t["date"]) == \
        ("41", BAD["to"], BAD["subject"], BAD["date"]), t
    assert fake.selected == ('"[Gmail]/Bozze"', True), fake.selected  # READ-ONLY
    assert set(fake.drafts) == {"41", "42"}, "a dry run deleted something"
    _no_writes(fake)


def test_zero_matches_refuses() -> None:
    fake = FakeIMAP([GOOD])
    out = gmail_drafts.delete_draft(_wire(fake), uid="41")

    assert out["ok"] is False and out["refused"] == "no draft matches", out
    assert out["match_count"] == 0 and out["matched"] == [], out
    assert set(fake.drafts) == {"42"}
    _no_writes(fake)


def test_multiple_matches_refuses() -> None:
    twins = [dict(BAD, message_id="<dup@example.test>"),
             dict(GOOD, message_id="<dup@example.test>")]
    fake = FakeIMAP(twins)
    out = gmail_drafts.delete_draft(_wire(fake), message_id="<dup@example.test>")

    assert out["ok"] is False, out
    assert out["refused"].startswith("more than one draft matches"), out
    assert out["match_count"] == 2, out
    assert [r["uid"] for r in out["matched"]] == ["41", "42"], out  # says WHAT it matched
    assert set(fake.drafts) == {"41", "42"}
    _no_writes(fake)


def test_no_drafts_folder_refuses_before_selecting() -> None:
    fake = FakeIMAP([BAD], drafts_folder=None)
    out = gmail_drafts.delete_draft(_wire(fake), uid="41", commit=True)

    assert out["ok"] is False and "\\Drafts" in out["refused"], out
    assert fake.selected is None, "selected a folder that is not Drafts"
    _no_writes(fake)


def test_non_draft_message_refuses() -> None:
    # Same folder, but the message carries no \Draft flag: whatever the folder
    # is called, this is not a draft.
    fake = FakeIMAP([dict(BAD, flags=r"41 (FLAGS (\Seen)")])
    out = gmail_drafts.delete_draft(_wire(fake), uid="41", commit=True)

    assert out["ok"] is False and "not flagged" in out["refused"], out
    assert set(fake.drafts) == {"41"}
    _no_writes(fake)


def test_message_id_narrows_never_widens() -> None:
    fake = FakeIMAP([BAD, GOOD])
    out = gmail_drafts.delete_draft(
        _wire(fake), uid="41", message_id="<good@example.test>", commit=True
    )

    assert out["ok"] is False and out["refused"] == "no draft matches", out
    assert set(fake.drafts) == {"41", "42"}, "a mismatched cross-check still deleted"
    _no_writes(fake)


def test_commit_moves_exactly_the_identified_message_to_trash() -> None:
    fake = FakeIMAP([BAD, GOOD])
    out = gmail_drafts.delete_draft(_wire(fake), uid="41", commit=True)

    assert out["ok"] is True and out["moved_to"] == "[Gmail]/Cestino", out
    assert out["target"]["uid"] == "41" and out["target"]["subject"] == BAD["subject"], out
    moves = [c for c in fake.commands if c[0] == "UID" and c[1] == "MOVE"]
    assert moves == [("UID", "MOVE", "41", '"[Gmail]/Cestino"')], moves  # ONE, by uid
    assert set(fake.drafts) == {"42"}, "the wrong draft went"
    assert fake.selected == ('"[Gmail]/Bozze"', False), fake.selected
    verbs = [c[1] for c in fake.commands if c[0] == "UID"]
    assert "STORE" not in verbs and "EXPUNGE" not in verbs, \
        f"delete must be recoverable (Trash), never an expunge: {fake.commands}"


def test_no_trash_folder_refuses_rather_than_expunge() -> None:
    fake = FakeIMAP([BAD], trash=None)
    out = gmail_drafts.delete_draft(_wire(fake), uid="41", commit=True)

    assert out["ok"] is False and "\\Trash" in out["refused"], out
    assert set(fake.drafts) == {"41"}
    _no_writes(fake)


def test_selector_required_and_validated() -> None:
    fake = FakeIMAP([BAD])
    settings = _wire(fake)

    bare = gmail_drafts.delete_draft(settings, commit=True)
    assert bare["ok"] is False and "name the draft" in bare["error"], bare

    junk = gmail_drafts.delete_draft(settings, uid="41 OR ALL", commit=True)
    assert junk["ok"] is False and "not an IMAP UID" in junk["error"], junk

    inject = gmail_drafts.delete_draft(settings, message_id='<a@b> ") OR ALL ("', commit=True)
    assert inject["ok"] is False and "IMAP SEARCH" in inject["error"], inject

    assert fake.commands == [], "a rejected selector still opened the mailbox"


def test_list_drafts_hands_out_the_uid() -> None:
    # Without a visible uid the operator cannot name the draft to delete, and
    # sequence numbers (what this used to fetch) shift under any other change.
    fake = FakeIMAP([BAD, GOOD])
    rows = gmail_drafts.list_drafts(_wire(fake))

    assert [r["uid"] for r in rows] == ["41", "42"], rows
    assert rows[0]["subject"] == BAD["subject"], rows
    assert all(c[1] != "STORE" for c in fake.commands if c[0] == "UID"), fake.commands


def test_cli_verb_exit_codes_and_passthrough() -> None:
    seen: dict = {}

    def fake_delete(settings, uid=None, message_id=None, commit=False):
        seen.update(uid=uid, message_id=message_id, commit=commit)
        return {"ok": bool(uid == "41"), "refused": "no draft matches"}

    cfg.load = lambda: types.SimpleNamespace()
    gmail_drafts.delete_draft = fake_delete
    try:
        ok = cli.cmd_draft_delete(types.SimpleNamespace(uid="41", message_id=None, commit=True))
        assert ok == 0, ok
        assert seen == {"uid": "41", "message_id": None, "commit": True}, seen

        refused = cli.cmd_draft_delete(
            types.SimpleNamespace(uid="99", message_id="<x@y>", commit=False)
        )
        assert refused == 1, "a refusal must not exit 0 — a script would read it as deleted"
        assert seen["commit"] is False and seen["message_id"] == "<x@y>", seen
    finally:
        gmail_drafts.delete_draft = _REAL_DELETE


def test_account_flag_refuses_the_verb() -> None:
    # It writes the operator's ONE Gmail credential; --account switches only the
    # engine profile, so answering "deleted" on another account would be a lie.
    called = {"n": 0}
    gmail_drafts.delete_draft = lambda *a, **k: called.update(n=called["n"] + 1)
    cfg.load = lambda: types.SimpleNamespace(
        prog_name="cs", email_address="support@example.test",
        engine_owner_uid="own-uid", account_map={"other": "other-uid"},
    )

    try:
        rc = cli.main(["--account", "other", "draft-delete", "41", "--commit"])
    finally:
        gmail_drafts.delete_draft = _REAL_DELETE

    assert rc == 2, f"expected the wrong-mailbox refusal, got {rc}"
    assert called["n"] == 0, "the verb ran against the wrong mailbox"


def run() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK: {name}")
    print("test_gmail_draft_delete: all assertions passed")


if __name__ == "__main__":
    run()
