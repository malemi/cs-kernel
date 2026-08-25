"""How the operator's DO-NOT-WRITE lists read an address. One matcher, so the
lists that hide a contact and the lists that block a send never disagree.

WHY THIS IS SHARED AND NOT TWO LOCAL HELPERS. Two lists decide who we leave
alone: `CS_SYSTEM_SENDERS` ("never a person waiting for an answer", read by the
`unanswered` sweep) and the `do_not_contact` table ("never write to them",
written by `cs suppress` and read by the producer worklist). They answer
different questions, but both are lists of addresses an operator TYPES, so a
typed entry has to mean the same thing in both. It briefly did not: the sweep
learned patterns while suppression kept matching exactly, which made
`cs suppress '*@<domain>'` remove the domain from the queue and STILL let
outreach mail it. A suppression that fails open is worse than no suppression at
all — it is silence the operator reads as protection — so the matcher lives in
one place and both callers import it.

An entry is a PATTERN only when it carries a wildcard; anything else is matched
exactly. That is what lets pattern support arrive without re-reading a single
list already in production.
"""
from __future__ import annotations

import fnmatch
from typing import Iterable

# The characters that turn an entry into a pattern. `[` is included because
# fnmatch reads it as a character class; an unclosed one it reads back as a
# literal `[`, so routing such an entry through fnmatch still matches it.
WILDCARD_CHARS = ("*", "?", "[")


def is_pattern(entry: str) -> bool:
    return any(c in entry for c in WILDCARD_CHARS)


class AddrSet:
    """A set of addresses that also understands fnmatch patterns.

    Deliberately a `__contains__` type rather than a pair of sets a caller must
    remember to consult: `email in addrs` is the question every call site was
    already asking, so upgrading the answer cannot leave one of them behind —
    which is exactly how the two lists drifted apart in the first place.

    Entries are stripped and lower-cased; blanks are dropped. Membership tests
    lower-case the probe too, so a caller may pass an address in any case.
    """

    __slots__ = ("literals", "patterns")

    def __init__(self, entries: Iterable[str] = ()) -> None:
        cleaned = {(e or "").strip().lower() for e in entries}
        cleaned.discard("")
        self.patterns = frozenset(e for e in cleaned if is_pattern(e))
        self.literals = frozenset(cleaned - self.patterns)

    def __contains__(self, email: object) -> bool:
        if not isinstance(email, str):
            return False
        e = email.strip().lower()
        if not e:
            return False
        if e in self.literals:
            return True  # the common case, and it needs no scan
        # `fnmatchcase`, not `fnmatch`: the latter runs `os.path.normcase` on
        # both sides, which is identity on POSIX but lower-cases on Windows.
        # Both sides are already lower-cased here, so the case-sensitive form is
        # the one whose result does not depend on the host.
        return any(fnmatch.fnmatchcase(e, p) for p in self.patterns)

    def __iter__(self):
        """The raw entries, patterns included — so `AddrSet(AddrSet(x))` is the
        identity and a caller can still print what was declared."""
        return iter(self.literals | self.patterns)

    def __len__(self) -> int:
        return len(self.literals) + len(self.patterns)

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"AddrSet(literals={len(self.literals)}, patterns={len(self.patterns)})"
