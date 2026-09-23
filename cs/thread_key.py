"""The RFC-5322 conversation key — the SAME key the engine stores as `thread_id`.

This is an ADDRESS, not a judgement. The charter says the engine owns what the
engine owns and the kernel must not re-derive its judgements; a thread key is
the opposite kind of thing — it is the identifier you need in order to ASK the
engine about a conversation, and it is defined by the message headers, not by
anybody's opinion of them. Re-deriving it here buys two things at no cost:

- the sweep can group Gmail messages into conversations OFFLINE, which is what
  makes "answered in this thread, to a different participant" expressible; and
- the key it computes is the same string the engine stored, so
  `emails.list_by_thread(thread_id=<this key>)` addresses the same conversation
  with no mapping table and no round trip to discover one.

The rule is the engine's own, transcribed rather than invented: first
whitespace-separated entry of `References`, else `In-Reply-To` whole, else the
message's own `Message-ID`. If the engine ever changes it, this changes with it
— the point is to agree, not to have an opinion.

Costs no extra IMAP work: `gmail_archive._fetch_headers` already asks for
MESSAGE-ID, REFERENCES and IN-REPLY-TO on both the inbound and the Sent side.

IDS ARRIVE HTML-ESCAPED AND THE KEY UNESCAPES THEM. A message id written
`&lt;id@host&gt;` is the same conversation as `<id@host>`: the escaping is a
corruption of the transport, never a distinction a mailer intends. Such ids
exist on the wire, in Gmail Sent and in the engine archive, so a reader that
takes them literally files our own reply under a conversation of its own and
the customer's thread is never settled — it is reported unanswered for ever,
and an operator that answers by itself answers twice. Normalising HERE, at the
single point every caller already funnels through, rejoins those rows without
rewriting one byte of stored mail.
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")

# Exactly what one pass of `html.escape(id, quote=True)` produces, inverted in
# one pass. One pass, not a loop to a fixed point: a single escaping is what
# the defect produces, and repeated unescaping would eat a literal `&amp;` that
# a mailer legitimately put in an id.
_ENTITY = re.compile(r"&(?:lt|gt|amp|quot|#39|#x27);", re.IGNORECASE)
_ENTITY_TEXT = {
    "&lt;": "<", "&gt;": ">", "&amp;": "&",
    "&quot;": '"', "&#39;": "'", "&#x27;": "'",
}


def unescape_ids(raw: str) -> str:
    """HTML-escaped angle brackets turned back into brackets.

    Only touches a value that carries an escaped bracket: `&lt;` or `&gt;` is
    the signature of the corruption, and without one there is nothing here to
    repair. That guard is what keeps a legitimate `&` in an id — rare, legal,
    and unrecoverable once mangled — out of the substitution entirely.
    """
    if "&lt;" not in raw.lower() and "&gt;" not in raw.lower():
        return raw
    return _ENTITY.sub(lambda m: _ENTITY_TEXT[m.group(0).lower()], raw)


def normalize_key(key: str | None) -> str:
    """Normalise a key a caller already holds — an engine-stored `thread_id`,
    say — to what `thread_key` would have produced for the same message.

    A caller that trusts a stored key and skips `thread_key` must still pass it
    through here, or the two disagree on exactly the rows this module exists to
    rejoin."""
    return _flat(key)


def _flat(raw: str | None) -> str:
    """Header value with folding collapsed to single spaces, stripped.

    Real mail folds long headers across lines; a References chain twenty ids
    long always is. Collapsing first means the split below sees ids, not
    line fragments.
    """
    if not raw:
        return ""
    flat = _WS.sub(" ", str(raw).replace("\r", " ").replace("\n", " ")).strip()
    return unescape_ids(flat)


def thread_key(
    message_id: str | None,
    references: str | None = None,
    in_reply_to: str | None = None,
) -> str:
    """Conversation key for one message; '' when the message has no usable id.

    An empty key means "cannot be threaded" and callers must fall back to
    something they own (the sweep falls back to the sender's address, which is
    exactly the pre-threading behaviour). Never guess a key: a wrong key merges
    two customers' conversations, and a merge is how one of them stops being
    raised.
    """
    refs = _flat(references)
    if refs:
        parts = refs.split()
        if parts:
            return parts[0]
    reply_to = _flat(in_reply_to)
    if reply_to:
        return reply_to
    return _flat(message_id)
