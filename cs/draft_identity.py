"""Exact mirror identity and conservative newly authored MIME content.

Bounded reads never turn a partial body or ambiguous quote extraction into proof.
The fingerprint names the complete MIME bytes observed, not their rendered text.
"""
from __future__ import annotations

import hashlib
import re
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

BODY_BYTES = 262144
ID_HEADER = 'X-CS-Engine-Draft-ID'
OWNER_HEADER = 'X-CS-Engine-Owner-UID'


def canonical_message_id(value: str | None) -> str | None:
    """Compare one conservative RFC ID, allowing only legal header folding.

    Callers must separately reject duplicate headers and parser defects. Never
    extract an ID from surrounding text or collapse whitespace inside the ID.
    """
    if not isinstance(value, str) or getattr(value, 'defects', ()):
        return None
    unfolded = re.sub(r'\r?\n(?=[ \t])', '', value).strip(' \t')
    if re.fullmatch(r'<[^<>\s@"\\()]+@[^<>\s@"\\()]+>', unfolded) is None:
        return None
    if any(not char.isascii() or not char.isprintable() for char in unfolded):
        return None
    try:
        parsed = policy.default.header_factory('Message-ID', unfolded)
    except (ValueError, IndexError):
        return None
    if parsed.defects:
        return None
    return unfolded


def validate_identity(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or value != value.strip() or any(c.isspace() or not c.isprintable() for c in value):
        raise ValueError('identity must be a nonempty opaque string without whitespace or controls')
    return value


def normalize_authored(text: str) -> str:
    return '\n'.join(' '.join(line.split()) for line in text.replace('\r', '').split('\n')).strip()


def authored_plain(text: str) -> tuple[str, str | None]:
    lines = []
    source_lines = text.splitlines()
    for index, line in enumerate(source_lines):
        if re.match(r'^\s*(On .+wrote:|Il .+ha scritto:|Le .+écrit\s*:|Am .+schrieb.+:|-----Original Message-----)\s*$', line, re.I):
            # A delimiter proves only the boundary, not that everything below
            # is quoted history. Bottom/inline replies remain material content.
            remainder = source_lines[index + 1:]
            if any(tail.strip() and not tail.lstrip().startswith('>') for tail in remainder):
                return '', 'ambiguous unquoted text after reply delimiter; authored text not compared'
            break
        if re.match(r'^\s*(On |Il |Le |Am ).+', line) and not lines:
            return '', 'ambiguous reply delimiter; authored text not compared'
        if line.lstrip().startswith('>'):
            continue
        if re.match(r'^\s*(From|Da|De):\s*.+', line, re.I):
            return '', 'ambiguous forwarded/reply header; authored text not compared'
        lines.append(line)
    return normalize_authored('\n'.join(lines)), None


class _AuthoredHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.skip = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.depth += 1
        attrs = dict(attrs)
        if self.skip is None and (tag in ('blockquote', 'script', 'style') or 'gmail_quote' in attrs.get('class', '') or attrs.get('id') == 'divRplyFwdMsg'):
            self.skip = self.depth
        if self.skip is None and tag in ('br', 'p', 'div', 'li'):
            self.parts.append('\n')
        if tag in ('br', 'img', 'hr', 'meta', 'input', 'link'):
            self.depth -= 1

    def handle_endtag(self, tag):
        if self.skip == self.depth:
            self.skip = None
        self.depth = max(0, self.depth - 1)
        if self.skip is None and tag in ('p', 'div', 'li'):
            self.parts.append('\n')

    def handle_data(self, data):
        if self.skip is None:
            self.parts.append(data)


def authored_message(raw: bytes) -> tuple[str, str | None]:
    if len(raw) >= BODY_BYTES:
        return '', 'bounded MIME body incomplete; authored text not compared'
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    if any(p.defects for p in msg.walk()):
        return '', 'malformed MIME body; authored text not compared'
    plain, rich = [], []
    for part in msg.walk():
        if part.is_multipart() or part.get_filename() or part.get_content_disposition() == 'attachment':
            continue
        if part.get_content_type() not in ('text/plain', 'text/html'):
            continue
        try:
            text = part.get_content(errors='strict')
        except (UnicodeError, LookupError, ValueError):
            return '', 'unreadable MIME text; authored text not compared'
        if part.get_content_type() == 'text/plain':
            plain.append(text)
        else:
            rich.append(text)
    if len(plain) > 1 or len(rich) > 1:
        return '', 'multiple body parts; authored text not compared'
    candidates = []
    if plain:
        authored, note = authored_plain(plain[0])
        if note:
            return '', note
        candidates.append(authored)
    if rich:
        parser = _AuthoredHTML()
        parser.feed(rich[0])
        if parser.skip is not None:
            return '', 'unclosed HTML quote; authored text not compared'
        authored, note = authored_plain(''.join(parser.parts))
        if note:
            return '', note
        candidates.append(authored)
    if candidates:
        # Every displayed alternative is evidence, including an empty one.
        # A matching plain fallback cannot hide a materially edited HTML body.
        if any(candidate != candidates[0] for candidate in candidates[1:]):
            return '', 'divergent MIME authored alternatives; authored text not compared'
        return candidates[0], None
    return '', 'no readable authored body'


def fingerprint(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
