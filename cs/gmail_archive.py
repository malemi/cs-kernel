"""Read the operator mailbox's Gmail directly (IMAP) as the dedup GROUND TRUTH.

WHY THIS EXISTS: the engine's archive misses mail sent BY HAND from Gmail —
it only records sends made through its own send tool, and does NOT ingest the
Gmail `[Gmail]/Sent Mail` folder (verified 2026-06-24: a hand-sent reply to a
customer is in Gmail Sent but `emails.search folder:sent` returns 0). So the
engine's "Sent archive" is NOT the dedup truth the docs assume it is. Until the
engine is fixed, and as defence-in-depth after, dedup reads Gmail itself.

Read-only: SEARCH/FETCH headers only, never writes. Reuses the IMAP login from
`gmail_drafts` (same app-password, same mailbox).

ONE mailbox per call — the operator's. Two readers here (`sent_to`,
`inbound_since`) decide nothing from "is this us" and therefore also exist as
`*_on(M, …)` variants that run on a caller-owned connection: that is what
`cs/mailboxes.py` fans out over every mailbox the company answers from. The
rest (`thread_with`, `inbound_recent`, `sent_recent`, `correspondence`) derive
direction or self-ness from `settings.email_address` and would misattribute
every message in somebody else's mailbox, so they stay single-mailbox.
"""
from __future__ import annotations

import email
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email import policy
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

from .config import Settings
from .gmail_drafts import _imap
from .thread_key import thread_key


def _parse_date(raw):
    """Parse an RFC-2822 Date header to a tz-aware datetime (UTC if naive)."""
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _imap_since(dt: datetime) -> str:
    """IMAP SEARCH SINCE token (DD-Mon-YYYY) for a datetime."""
    return dt.strftime("%d-%b-%Y")


class ChunkFetchFailed(Exception):
    """A batched header FETCH came back non-OK, so `chunk` messages are missing.

    Raised rather than swallowed. The old behaviour was `continue`, which
    discarded up to 200 messages per failure and returned a SHORT LIST that
    looks exactly like a complete one — and every caller here answers a question
    where a short list means "nothing found": has this contact written to us,
    who is still waiting. An absence nobody established is the failure mode
    `cs/mailboxes.py` exists to prevent, so it is never inferred from a read
    that did not happen.

    Callers catch this and report it. What they must NOT do is fold it into a
    channel that already means something else — see `cs/unanswered.py`'s
    `read_incomplete`, which is separate from `note` for exactly that reason."""


def _fetch_headers(M, ids, chunk: int = 200):
    """Batch BODY.PEEK header FETCH over a list of UID byte-strings, yielding
    parsed email.message objects. One FETCH per `chunk` UIDs (not one per UID) —
    the bulk path. Read-only (PEEK).

    Raises `ChunkFetchFailed` if any chunk comes back non-OK."""
    out = []
    for i in range(0, len(ids), chunk):
        batch = ids[i : i + chunk]
        typ, data = M.uid(
            "FETCH",
            b",".join(batch),
            "(BODY.PEEK[HEADER.FIELDS (DATE FROM TO CC BCC SUBJECT MESSAGE-ID REFERENCES IN-REPLY-TO)])",
        )
        if typ != "OK" or not data:
            raise ChunkFetchFailed(
                f"a batched header FETCH over {len(batch)} message(s) returned "
                f"{typ!r} — those messages were not read"
            )
        for part in data:
            if isinstance(part, tuple) and part[1]:
                out.append(email.message_from_bytes(part[1], policy=policy.default))
    return out


def headers_for_addresses_on(M, addrs, key: str, flag: str, default: str,
                             since=None) -> list[dict]:
    """Every message in one folder involving ANY of `addrs`, in ONE search plus
    chunked header FETCHes — the bulk twin of `sent_to_on` / `inbound_since_on`.

    Those two answer about ONE address and issue one FETCH round trip per
    matching UID. Asked once per contact per mailbox that is O(contacts x
    mailboxes x messages) round trips, and on a mailbox that holds one of the
    contacts' own sent history it was 21,637 of them for a single pair. This
    asks the whole question once: `OR`-composed SEARCH, then `_fetch_headers`.

    `key` is "TO" (Sent) or "FROM" (All Mail). Rows carry `date`, `subject`,
    `message_id` and `matched` — the address this row is evidence about, which
    is what makes bucketing possible in the caller.

    **Matching is reproduced, not assumed.** Measured against Gmail: a `TO`
    search matches the Cc header too (37 To / 14 Cc / 0 Bcc over one Sent
    folder), so the To-side bucket reads To+Cc; a `FROM` search matched the
    From header and nothing else (133 of 133), so the From-side bucket reads
    From. Substring matching was refuted (0 hits over 25 contacts). `Bcc` is
    fetched but never bucketed on: whether the server matches it is unknown —
    no message in the sampled folder carries one — so a Bcc-only match is
    REPORTED rather than silently counted or silently dropped."""
    addrs = [a for a in addrs if a]
    if not addrs:
        return []
    folder = _find_folder(M, flag, default)
    M.select(f'"{folder}"', readonly=True)

    terms: list = []
    for a in addrs[:-1]:
        terms += ["OR", key, a]
    terms += [key, addrs[-1]]
    if since is not None:
        terms += ["SINCE", _imap_since(since)]
    typ, d = M.uid("SEARCH", None, *terms)
    ids = d[0].split() if (typ == "OK" and d and d[0]) else []
    if not ids:
        return []

    wanted = {a.lower() for a in addrs}
    fields = ("To", "Cc") if key == "TO" else ("From",)
    out = []
    for h in _fetch_headers(M, ids):
        hit = set()
        for f in fields:
            hit |= {e.lower() for _n, e in getaddresses([str(h.get(f) or "")])}
        matched = sorted(hit & wanted)
        row = {
            "date": h.get("Date"),
            "subject": h.get("Subject"),
            "message_id": str(h.get("Message-ID") or ""),
        }
        if matched:
            for a in matched:
                out.append({**row, "matched": a})
            continue
        # The server returned it and none of the bucketed headers explain why.
        # Measured cause when it happens: the address is in Bcc. Reported, not
        # counted — an unknown resolved silently in either direction is the
        # thing this module exists to stop.
        bcc = {e.lower() for _n, e in getaddresses([str(h.get("Bcc") or "")])}
        for a in sorted(bcc & wanted):
            out.append({**row, "matched": a, "bcc_only": True})
    return out


def _find_folder(M, flag: str, default: str) -> str:
    """Folder carrying a given special-use flag (locale-proof), e.g. \\Sent, \\All."""
    typ, data = M.list()
    if typ == "OK":
        for raw in data or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
            if flag in line.lower() and '"' in line:
                return line.rsplit('"', 2)[-2]
    return default


def _hdr(M, uid: bytes):
    typ, md = M.uid(
        "FETCH",
        uid,
        "(BODY.PEEK[HEADER.FIELDS (DATE FROM TO SUBJECT MESSAGE-ID REFERENCES IN-REPLY-TO)])",
    )
    if typ != "OK" or not md or not md[0]:
        return None
    return email.message_from_bytes(md[0][1], policy=policy.default)


def sent_to_on(M, addr: str, days: int | None = None) -> list[dict]:
    """`sent_to`, on a connection the CALLER owns and keeps open.

    Split out for the cross-mailbox fan-out (`cs/mailboxes.py`), which holds one
    session per mailbox for the whole process: the per-call TLS + LOGIN + LIST +
    SELECT is the entire cost of reading N mailboxes, and a function that
    logs out cannot be called twice cheaply. This decides nothing from "is this
    us", which is what makes it safe to run against a mailbox that is not the
    operator's."""
    sent = _find_folder(M, "\\sent", "[Gmail]/Sent Mail")
    M.select(f'"{sent}"', readonly=True)
    typ, d = M.uid("SEARCH", None, "TO", addr)
    ids = d[0].split() if d and d[0] else []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    out = []
    for uid in ids:
        h = _hdr(M, uid)
        if not h:
            continue
        raw = h.get("Date")
        dt = None
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt is not None and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                dt = None
        if cutoff is not None and (dt is None or dt < cutoff):
            continue
        out.append({"date": raw, "subject": h.get("Subject"),
                    "message_id": h.get("Message-ID")})
    return out


def sent_to(settings: Settings, addr: str, days: int | None = None) -> list[dict]:
    """Messages in Gmail's Sent folder addressed TO `addr` — the dedup truth.

    A non-empty result means the operator actually wrote to them (INCLUDING
    replies sent by hand, which the engine never sees). When `days` is given, the window
    is computed from each message's own Date header — NOT IMAP SINCE, whose
    INTERNALDATE the live engine re-touches on every sync, which made the same
    query flip between runs.

    ONE mailbox: the operator's. It answers "did WE write", where "we" is this
    one mailbox — see `cs/mailboxes.sent_to_across` for the same question asked
    of every mailbox the company answers from."""
    M = _imap(settings)
    try:
        return sent_to_on(M, addr, days)
    finally:
        try:
            M.logout()
        except Exception:
            pass


#: How far back `sent_body_match` reads bodies for one contact. Headers are
#: cheap and bodies are not, so the comparison is bounded rather than windowed
#: by days: a draft that repeats a mail delivered more than this many messages
#: ago is not the failure this check exists for (a compose that ran twice, one
#: copy sent and one left behind), and the other verdicts still cover it.
BODY_MATCH_SCAN = 20

#: Bytes of each Sent message fetched for the duplicate comparison.
#:
#: `BODY.PEEK[]` pulls the entire MIME tree, attachments included: 86 MiB over a
#: 120-message sample, ~717 KiB per message, to compare a body `_normalise`
#: truncates at BODY_MAX characters. A bounded prefix carries the headers and
#: the leading text part — attachments come after — and is parsed by exactly the
#: same code, so no MIME reconstruction is involved and nothing about the
#: comparison changes. Measured over that sample: byte-identical `_normalise`
#: output on 120 of 120 messages, 1.8% of the bytes, 162s -> 24s.
BODY_PREFIX_BYTES = 65536


def sent_body_match(settings: Settings, addr: str, body: str,
                    limit: int = BODY_MATCH_SCAN) -> tuple[dict | None, str | None]:
    """`(match, note)` — the Sent message to `addr` carrying this same text.

    Answers "has this exact reply already been delivered to this person?" —
    the one question that separates a draft the conversation moved past from a
    SECOND COPY of a mail the customer already has. Sending that copy mails
    them the same thing twice, so it deserves its own verdict rather than
    being folded into "somebody answered another way".

    Bodies are compared after `_normalise` (the same collapse every other
    reader here applies), never raw: the delivered copy has been through MIME
    encoding and line folding, so byte equality on the wire form would never
    fire. A markdown-rendered send whose plain-text part no longer matches the
    source simply does not match — a miss costs the caller nothing beyond the
    verdict it would have had anyway.

    Two limits, and both are REPORTED rather than swallowed, because a silent
    limit reads as "checked everything" when it did not:

    - `_normalise` truncates at BODY_MAX, so two long mails sharing a
      BODY_MAX-character prefix would compare equal. A body that reaches the
      cap is therefore not compared at all — a false `duplicate` on a draft
      that only STARTS like a delivered mail is worse than no verdict.
    - at most `limit` bodies are fetched, newest first. When there are more
      messages to that contact than that, the note says how many were read.

    Read-only. The `(value, note)` shape is the module's degradation contract,
    the same one `engine_view.settled` uses.
    """
    wanted = _normalise(body or "")
    if not wanted:
        return None, None
    if len(wanted) >= BODY_MAX:
        return None, (f"the draft to {addr} is longer than {BODY_MAX} characters "
                      f"— too long to compare against Sent without risking a "
                      f"false match, so it was not compared")
    # The SHARED session, not a private login. Every other reader here reuses
    # `mailboxes.session()`; this one opened its own TLS+LOGIN and logged out
    # again on every call — 1.22s of the cost of each one, paid once per draft.
    from . import mailboxes

    M = mailboxes.session(settings, mailboxes.operator_mailbox(settings))
    try:
        sent = _find_folder(M, "\\sent", "[Gmail]/Sent Mail")
        M.select(f'"{sent}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "TO", addr)
        ids = d[0].split() if (typ == "OK" and d and d[0]) else []
        scanned = list(reversed(ids))[:limit]
        if not scanned:
            # Nothing has been sent to this address, so no copy can exist —
            # and an empty sequence-set is not a FETCH the server accepts.
            return None, None
        truncated = 0
        # ONE round trip for the whole scan, not one per message. Bounding the
        # prefix made each fetch small, which moved the cost back onto the
        # round trips themselves: 20 of them per contact, once per draft.
        typ, md = M.uid("FETCH", b",".join(scanned),
                        f"(BODY.PEEK[]<0.{BODY_PREFIX_BYTES}>)")
        if typ != "OK" or not md:
            return None, (f"could not read the messages sent to {addr} "
                          f"(FETCH returned {typ!r}), so no duplicate check "
                          f"was made")
        for part in md:
            if not isinstance(part, tuple) or not part[1]:
                continue
            if len(part[1]) >= BODY_PREFIX_BYTES:
                truncated += 1
            msg = email.message_from_bytes(part[1], policy=policy.default)
            delivered, _files = _body_and_attachments(msg)
            if delivered and delivered == wanted:
                return {
                    "date": str(msg.get("Date") or ""),
                    "subject": str(msg.get("Subject") or ""),
                    "message_id": str(msg.get("Message-ID") or ""),
                }, None
        if len(ids) > len(scanned):
            return None, (f"read the newest {len(scanned)} of {len(ids)} messages "
                          f"sent to {addr} — an older identical copy would not "
                          f"have been seen")
        if truncated:
            # A miss, never a false match: the comparison is exact equality, so
            # a body cut short can only fail to match. Said out loud anyway —
            # a limit nobody is told about reads as "checked everything".
            return None, (f"{truncated} message(s) to {addr} are longer than "
                          f"{BODY_PREFIX_BYTES} bytes and were compared on their "
                          f"first {BODY_PREFIX_BYTES}; a duplicate whose text "
                          f"begins beyond that would not have been seen")
        return None, None
    finally:
        # The session is shared and stays open for the rest of the run; closing
        # it here is what made every call pay a fresh login.
        pass


def correspondence(settings: Settings, addr: str) -> list[dict]:
    """Real history with `addr`, both directions, DRAFT-FREE by construction.

    - our sends = the Sent folder, TO `addr` (drafts live in Drafts, never Sent);
    - their inbound = All Mail, FROM `addr` (a draft is FROM the operator
      mailbox, so it can never match FROM the contact).

    So a draft we just queued never counts as history (the trap that made a cold
    contact read as 'reply in thread'). Each row carries `direction` (sent|in)."""
    M = _imap(settings)
    try:
        out = []
        sent = _find_folder(M, "\\sent", "[Gmail]/Sent Mail")
        M.select(f'"{sent}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "TO", addr)
        for uid in (d[0].split() if d and d[0] else []):
            h = _hdr(M, uid)
            if h:
                out.append({"date": h.get("Date"), "from": h.get("From") or "",
                            "to": h.get("To") or "", "subject": h.get("Subject"),
                            "direction": "sent"})
        allm = _find_folder(M, "\\all", "[Gmail]/All Mail")
        M.select(f'"{allm}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "FROM", addr)
        for uid in (d[0].split() if d and d[0] else []):
            h = _hdr(M, uid)
            if h:
                out.append({"date": h.get("Date"), "from": h.get("From") or "",
                            "to": h.get("To") or "", "subject": h.get("Subject"),
                            "direction": "in"})
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass


def inbound_since_on(M, addr: str, after=None) -> list[dict]:
    """`inbound_since`, on a connection the CALLER owns and keeps open — same
    split, and for the same reason, as `sent_to_on`.

    Fannable across mailboxes because it names no self: it matches FROM the
    contact and reads nothing from `settings.email_address`. (`inbound_recent`
    and `thread_with` do, which is why neither is fanned out.)"""
    allm = _find_folder(M, "\\all", "[Gmail]/All Mail")
    M.select(f'"{allm}"', readonly=True)
    typ, d = M.uid("SEARCH", None, "FROM", addr)
    ids = d[0].split() if d and d[0] else []
    out = []
    for uid in ids:
        h = _hdr(M, uid)
        if not h:
            continue
        raw = h.get("Date")
        dt = None
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt is not None and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                dt = None
        if after is not None and (dt is None or dt <= after):
            continue
        out.append({"date": raw, "subject": h.get("Subject")})
    return out


def inbound_since(settings: Settings, addr: str, after=None) -> list[dict]:
    """Customer messages FROM `addr` (All Mail), optionally only those whose Date
    header is strictly after `after` (a tz-aware datetime) — GROUND TRUTH for
    'did they reply'. Independent of engine sync state. A message FROM the
    contact can never be one of our drafts, so this is draft-free by nature.

    ONE mailbox: the operator's. `cs/mailboxes.inbound_since_across` asks it of
    every mailbox the company answers from."""
    M = _imap(settings)
    try:
        return inbound_since_on(M, addr, after)
    finally:
        try:
            M.logout()
        except Exception:
            pass


def inbound_recent(settings: Settings, days: int) -> list[dict]:
    """Every INBOUND message in All Mail whose Date HEADER is within the last
    `days` — the deterministic candidate feed for the unanswered sweep.

    The IMAP SEARCH is bounded by SINCE (cutoff - 3d margin) for efficiency, but
    the precise window is enforced on the Date HEADER, never INTERNALDATE (the
    engine sync re-touches INTERNALDATE and makes SINCE-only queries flip between
    runs — same caveat as `sent_to`). Messages FROM the operator itself (i.e. our
    own sends, which All Mail also holds) are dropped here. Read-only.

    SINGLE-MAILBOX, and not fannable as it stands: "inbound" here means "not
    from the operator" (`self_addr` below), so run against another mailbox it
    would count that mailbox's own sends as inbound customer mail. Widening it
    is separate work with its own correctness question.

    Each row: {email, name, date (tz-aware), subject, message_id, thread_key}.
    `thread_key` is the conversation this message belongs to (`cs/thread_key.py`)
    and costs nothing: REFERENCES and IN-REPLY-TO are already in the one FETCH
    above. It is what lets the sweep ask "was this CONVERSATION answered"
    instead of "was this ADDRESS written to", which are different questions
    whenever a thread has more than one participant."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    self_addr = (settings.email_address or "").strip().lower()
    M = _imap(settings)
    try:
        allm = _find_folder(M, "\\all", "[Gmail]/All Mail")
        M.select(f'"{allm}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "SINCE", _imap_since(cutoff - timedelta(days=3)))
        ids = d[0].split() if d and d[0] else []
        out = []
        for h in _fetch_headers(M, ids):
            dt = _parse_date(h.get("Date"))
            if dt is None or dt < cutoff:
                continue
            name, addr = parseaddr(h.get("From") or "")
            addr = (addr or "").strip().lower()
            if not addr or addr == self_addr:
                continue
            out.append(
                {
                    "email": addr,
                    "name": name or "",
                    "date": dt,
                    "subject": h.get("Subject") or "",
                    "message_id": h.get("Message-ID") or "",
                    "thread_key": thread_key(
                        h.get("Message-ID"), h.get("References"), h.get("In-Reply-To")
                    ),
                }
            )
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass


def _part_text(part) -> str:
    """Decoded text of one non-multipart part; '' when it cannot be decoded."""
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


class _HTMLToText(HTMLParser):
    """HTML -> text for HTML-only mail, via the stdlib parser.

    Deliberately NOT a regex: a tag-stripping regex over real mail HTML both
    leaks markup (conditional comments, unclosed tags) and swallows content,
    and the text is fed to a model that then answers a customer. Block-level
    tags become newlines so paragraphs survive; script/style are dropped."""

    _BLOCK = {"p", "div", "br", "tr", "li", "ul", "ol", "table", "blockquote",
              "h1", "h2", "h3", "h4", "h5", "h6", "pre", "hr"}
    _SKIP = {"script", "style", "head", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        elif tag in self._BLOCK:
            self._out.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in self._BLOCK:
            self._out.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._out.append(data)

    def text(self) -> str:
        return "".join(self._out)


def _html_to_text(raw: str) -> str:
    p = _HTMLToText()
    try:
        p.feed(raw)
        p.close()
    except Exception:
        return ""
    return p.text()


_SPACES = re.compile(r"[ \t\f\v]+")
_BLANKS = re.compile(r"\n{3,}")
BODY_MAX = 4000  # chars kept per message body — enough to reply, small enough to prompt


def _normalise(text: str, limit: int = BODY_MAX) -> str:
    """Collapse runs of spaces/blank lines, strip, truncate at `limit` chars."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _BLANKS.sub("\n\n", text).strip()[:limit]


def _body_and_attachments(msg) -> tuple[str, list[str]]:
    """(body, attachment filenames) of a parsed message.

    text/plain wins; an HTML-only mail is tag-stripped. Attachment parts (and
    any part carrying a filename, e.g. an inline screenshot) contribute their
    FILENAME only, never body text — base64 in a prompt is noise."""
    plain, html_alt, files = [], [], []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if (part.get_content_disposition() or "").lower() == "attachment" or filename:
            files.append(filename or f"(unnamed {part.get_content_type()})")
            continue
        ctype = part.get_content_type()
        if ctype == "text/plain":
            plain.append(_part_text(part))
        elif ctype == "text/html":
            html_alt.append(_html_to_text(_part_text(part)))
    body = "\n\n".join(p for p in plain if p.strip())
    if not body.strip():
        body = "\n\n".join(p for p in html_alt if p.strip())
    return _normalise(body), files


def thread_with(settings: Settings, addr: str, limit: int = 20) -> list[dict]:
    """Every message exchanged with `addr` (All Mail), NEWEST FIRST, with bodies.

    The ground-truth conversation reader: one read-only IMAP session
    (`BODY.PEEK`, never a flag change), All Mail so it covers both directions
    — our sends and their replies — independent of any engine sync state. The
    newest inbound is simply the first element with `outbound is False`.

    DRAFT-FREE: All Mail also holds unsent drafts, and Gmail expresses their
    draft-ness only as the `\\Draft` X-GM-LABEL (the IMAP `\\Draft` FLAG is not
    set, so an `UNDRAFT` search does NOT exclude them — verified 2026-07-25).
    They are dropped here: a queued draft is a mail the customer never got,
    and feeding it back as something "we wrote" would ground a reply in a
    conversation that never happened.

    Each row:
      date         tz-aware datetime | None (from the Date HEADER)
      from_addr    bare lowercased address
      outbound     True when we sent it (from_addr == the operator mailbox)
      subject      str ('' when absent)
      message_id   angle-bracketed Message-ID, '' when absent
      references   References header, whitespace-normalised, '' when absent
      body         text/plain (or tag-stripped HTML), truncated at BODY_MAX
      attachments  filenames only

    `limit` keeps the newest N messages of the conversation (0 = all).

    SINGLE-MAILBOX, and not fannable as it stands: `outbound` is decided by
    comparing the sender against `settings.email_address`, so in another
    mailbox every row's direction would be wrong."""
    addr = (addr or "").strip().lower()
    self_addr = (settings.email_address or "").strip().lower()
    M = _imap(settings)
    try:
        allm = _find_folder(M, "\\all", "[Gmail]/All Mail")
        M.select(f'"{allm}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "OR", "FROM", f'"{addr}"', "TO", f'"{addr}"')
        ids = d[0].split() if (typ == "OK" and d and d[0]) else []
        out = []
        labels = True  # X-GM-LABELS is a Gmail extension; degrade on other servers
        # UIDs ascend with arrival: walk from the newest back and stop once
        # `limit` REAL messages are in hand (drafts are skipped, not counted).
        for uid in reversed(ids):
            if limit and limit > 0 and len(out) >= limit:
                break
            typ, md = "NO", None
            if labels:
                try:
                    typ, md = M.uid("FETCH", uid, "(X-GM-LABELS BODY.PEEK[])")
                except imaplib.IMAP4.error:
                    labels = False
            if not labels:
                typ, md = M.uid("FETCH", uid, "(BODY.PEEK[])")
            if typ != "OK" or not md or not isinstance(md[0], tuple) or not md[0][1]:
                continue
            line = md[0][0].decode(errors="replace") if md[0][0] else ""
            if "\\Draft" in line:  # matches both the \Draft and escaped \\Draft forms
                continue
            msg = email.message_from_bytes(md[0][1], policy=policy.default)
            mid = str(msg.get("Message-ID") or "").strip()
            if mid and not mid.startswith("<"):
                mid = f"<{mid}>"
            from_addr = (parseaddr(str(msg.get("From") or ""))[1] or "").strip().lower()
            body, files = _body_and_attachments(msg)
            out.append(
                {
                    "date": _parse_date(msg.get("Date")),
                    "from_addr": from_addr,
                    "outbound": bool(from_addr) and from_addr == self_addr,
                    "subject": str(msg.get("Subject") or ""),
                    "message_id": mid,
                    "references": _SPACES.sub(
                        " ", str(msg.get("References") or "").replace("\n", " ")
                    ).strip(),
                    "body": body,
                    "attachments": files,
                }
            )
        # Date header order, newest first; undated messages sink to the bottom
        # keeping their UID-descending order (sort is stable).
        floor = datetime.min.replace(tzinfo=timezone.utc)
        out.sort(key=lambda m: m["date"] or floor, reverse=True)
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass


def sent_recent(settings: Settings, days: int) -> list[dict]:
    """Every Sent message whose Date HEADER is within the last `days`. Same
    Date-header windowing + SINCE margin as `inbound_recent`. Read-only.

    Each row: {to (list of bare lowercased addresses from To+Cc), date,
    thread_key}. `thread_key` is the conversation the message answers — the
    same key `inbound_recent` puts on the other side, so the two join without a
    round trip. It is what makes an answer sent to a thread's PRINCIPAL count
    for the colleague who was only in Cc."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    M = _imap(settings)
    try:
        sent = _find_folder(M, "\\sent", "[Gmail]/Sent Mail")
        M.select(f'"{sent}"', readonly=True)
        typ, d = M.uid("SEARCH", None, "SINCE", _imap_since(cutoff - timedelta(days=3)))
        ids = d[0].split() if d and d[0] else []
        out = []
        for h in _fetch_headers(M, ids):
            dt = _parse_date(h.get("Date"))
            if dt is None or dt < cutoff:
                continue
            addrs = [
                a.strip().lower()
                for _, a in getaddresses([h.get("To") or "", h.get("Cc") or ""])
                if a and a.strip()
            ]
            out.append(
                {
                    "to": addrs,
                    "date": dt,
                    "thread_key": thread_key(
                        h.get("Message-ID"), h.get("References"), h.get("In-Reply-To")
                    ),
                }
            )
        return out
    finally:
        try:
            M.logout()
        except Exception:
            pass
