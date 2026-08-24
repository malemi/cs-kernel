"""Campaign packs — a campaign's reusable "intelligence" as DATA in the
clone repo, run by KERNEL code.

A pack is data + templates + prose; the runner is kernel code
(cs/campaign.py `send_reminder` / `send_sms`). This respects the
extensions rule: the machinery (lifecycle, gates, sending) is shared and
lives in the kernel; what varies per campaign is CONTENT, and it lives in
the clone under ``campaigns/<pack-name>/`` (git-tracked company data).
Months later, "have we ever done something like this?" is answered by
reading the packs (`cs campaign packs`), and re-running one is
copy-and-edit — no new one-off script, no dedicated cron.

Pack layout (in the CLONE repo)::

    campaigns/<pack-name>/
    ├── campaign.toml      # [pack] kind/description/campaign/status/dates/
    │                      #        confirm_question; [windows] optional
    │                      #        overrides of the [knobs] windows/caps
    ├── mail_first.md      # templates: first line `Subject: …`, blank line,
    ├── mail_reminder.md   # then a markdown body with {placeholders} filled
    │                      # from the contact row (dossier + email), rendered
    │                      # through send_mail's md→plain+html pipeline
    ├── sms.txt            # SMS text, same {placeholders}
    ├── builders.py        # OPTIONAL hook for rich hand-built HTML —
    │                      # build(row) / build_reminder(row) → (subject,
    │                      # plain, html). Takes precedence over templates.
    ├── playbook.md        # the operator playbook: how it ran, the gotchas
    └── legacy/            # OPTIONAL superseded one-off code, never imported

Loud by design: a missing placeholder, a missing template AND builder, or
a broken campaign.toml raises :class:`PackError` — the runner refuses
rather than sending broken copy. A fixed-template action whose campaign
has NO pack at all is refused loudly by the campaign handlers (the kernel
never invents copy).

WHEN A CAMPAIGN IS OVER
-----------------------
A campaign that has ended must not be able to deliver anything. Two
declarations in ``[pack]`` say so, and both are enforced (2026-08-24 —
before this, neither was read by anything):

``status``
    ``active`` or ``done``, and nothing else — an unrecognised word is a
    :class:`PackError` at load, never a silent pass. ``done`` refuses every
    delivery path. This is the primary gate and it is the one a human sets
    by hand.

``ends_on``
    The backstop for when the human forgets. A date (``ends_on =
    2026-07-31``, or the ISO string) past which the pack refuses to deliver
    EVEN WHILE ``status = "active"`` — which is exactly the shape of the
    2026-08-23 near miss: a July migration pack still declaring itself
    active in late August, one tick away from telling 26 customers their
    number changes on a date three weeks past. A campaign with no end
    declares ``ends_on = "never"`` and delivers indefinitely. Anything else
    — a malformed date, prose, an empty string — is a :class:`PackError` at
    load: "cannot read the end date, so assume no limit" is precisely how
    this class of bug survives.

``dates`` is NOT either of them. It stays free prose for the reader ("first
notice → decommission"), it is never parsed, and it gates nothing. A
parser over a field that legitimately holds ``continuous from 2026-08``
would half-work, and a half-working gate on a send path is worse than none:
``ends_on`` is typed precisely so the two jobs stay separate.

A pack that is ``active`` and declares no ``ends_on`` at all still delivers
— the open-ended onboarding loop is a real shape and must never acquire an
expiry by accident — but it carries :meth:`Pack.undeclared_end_note`, which
the worklist surfaces so the omission is visible rather than assumed.
"""
from __future__ import annotations

import importlib.util
import os
import tomllib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

KINDS = ("fixed-template", "composed-draft")

# [pack].status — the primary delivery gate. Two values, because a campaign is
# either running or over; a third would only be a synonym for one of these, and
# a synonym on a send gate is a place for a typo to hide.
STATUSES = ("active", "done")

# The explicit "this campaign has no end" value of [pack].ends_on. Spelled out
# rather than left implicit so that a missing key and a deliberate open-ended
# campaign are DIFFERENT states: the second is a decision, the first is silence.
ENDS_ON_NEVER = "never"


class PackError(RuntimeError):
    """A pack is missing, malformed, or cannot render — refuse loudly."""


class _StrictRow(dict):
    """format_map helper: a missing placeholder is an ERROR, not an empty
    string — never send a mail with a hole in it."""

    def __missing__(self, key):  # pragma: no cover - exercised via format_map
        raise KeyError(key)


@dataclass
class Pack:
    path: Path
    name: str                 # engine campaign name (default: directory name)
    kind: str                 # fixed-template | composed-draft
    description: str = ""     # one line — what the discovery search reads
    status: str = "active"    # active | done — the primary delivery gate
    dates: str = ""           # PROSE for the reader: when it ran. Gates NOTHING.
    # The typed end-of-life backstop (see the module docstring). Three states,
    # which is why it takes two fields: no key at all (undeclared — delivers,
    # and says so), `ends_on = "never"` (declared open-ended), or a real date.
    ends_on: Optional[date] = None
    ends_on_declared: bool = False
    confirm_question: str = ""
    # [windows] — per-pack overrides of the [knobs] windows/caps (None = knob)
    reminder_after_hour: Optional[int] = None
    sms_hour: Optional[int] = None
    reminder_max: Optional[int] = None

    _builders: Any = None     # loaded builders module (or None)

    # ---------------------------------------------------------------- build

    def _render_template(self, filename: str, row: dict) -> tuple[str, str, str]:
        p = self.path / filename
        if not p.exists():
            raise PackError(f"{self.path.name}: missing {filename} (and no builders.py hook)")
        text = p.read_text(encoding="utf-8")
        first, _, rest = text.partition("\n")
        if not first.lower().startswith("subject:"):
            raise PackError(
                f"{self.path.name}/{filename}: first line must be 'Subject: …'"
            )
        subject_tpl = first.split(":", 1)[1].strip()
        body_tpl = rest.lstrip("\n")
        try:
            subject = subject_tpl.format_map(_StrictRow(row))
            body_md = body_tpl.format_map(_StrictRow(row))
        except KeyError as e:
            raise PackError(
                f"{self.path.name}/{filename}: missing placeholder {e} in contact row — "
                "fix the contact dossier or add a builders.py that handles it"
            ) from None
        from . import send_mail  # md→plain+html pipeline (single implementation)

        return subject, send_mail.md_to_plain(body_md), send_mail.md_to_html(body_md)

    def build(self, row: dict) -> tuple[str, str, str]:
        """First-notice mail → (subject, plain, html). builders.build wins."""
        if self._builders is not None and hasattr(self._builders, "build"):
            return tuple(self._builders.build(row))
        return self._render_template("mail_first.md", row)

    def build_reminder(self, row: dict) -> tuple[str, str, str]:
        """Reminder mail → (subject, plain, html). builders.build_reminder wins."""
        if self._builders is not None and hasattr(self._builders, "build_reminder"):
            return tuple(self._builders.build_reminder(row))
        return self._render_template("mail_reminder.md", row)

    def sms_text(self, row: dict) -> str:
        p = self.path / "sms.txt"
        if not p.exists():
            raise PackError(f"{self.path.name}: missing sms.txt")
        try:
            return p.read_text(encoding="utf-8").strip().format_map(_StrictRow(row))
        except KeyError as e:
            raise PackError(
                f"{self.path.name}/sms.txt: missing placeholder {e} in contact row"
            ) from None

    # ------------------------------------------------------- is it over?

    def effective_status(self, today: date) -> str:
        """What the campaign IS today — ``active``, ``done`` or ``ended``.

        ``ended`` has no spelling in campaign.toml on purpose: it is what an
        ``active`` pack becomes once it is past its own ``ends_on``, i.e. the
        state of a campaign whose owner finished it and forgot to say so.
        """
        if self.status != "active":
            return self.status
        if self.ends_on is not None and today > self.ends_on:
            return "ended"
        return "active"

    def delivery_refusal(self, today: date) -> Optional[str]:
        """One sentence naming why this pack may not put a message in front of
        a customer today — or ``None`` when it may.

        EVERY delivery path reads this: the worklist, the first notice, the
        reminder, the SMS, the composed draft. A refusal always names the
        reason AND the date, because a contact that quietly disappears from a
        worklist is the failure this gate exists to stop.
        """
        effective = self.effective_status(today)
        if effective == "active":
            return None
        where = f"[pack] in {self.path / 'campaign.toml'}"
        if effective == "ended":
            return (
                f"campaign '{self.name}' ended on {self.ends_on.isoformat()} and "
                f"today is {today.isoformat()} — REFUSING to deliver. Its "
                f'status still says "active" ({where}): set it to "done", or '
                f"move ends_on if the campaign is genuinely still running."
            )
        ran = f" (dates: {self.dates})" if self.dates else ""
        return (
            f"campaign '{self.name}' is finished — status = \"{self.status}\" "
            f"in {where}{ran} — REFUSING to deliver on {today.isoformat()}."
        )

    def undeclared_end_note(self) -> Optional[str]:
        """The advisory for an active pack that never said when it ends.

        Not a refusal: an open-ended campaign is a real shape and must keep
        delivering indefinitely. But "nobody declared an end" and "this
        campaign has no end" are different facts, and only the second is a
        decision — so the first is reported until someone writes down which
        one it is.
        """
        if self.status != "active" or self.ends_on_declared:
            return None
        return (
            f"campaign '{self.name}' declares no [pack].ends_on — it will "
            f"deliver for ever. Add a date, or ends_on = \"{ENDS_ON_NEVER}\" if "
            f"that is the intention ({self.path / 'campaign.toml'})."
        )

    def summary(self, today: Optional[date] = None) -> dict:
        """Discovery shape for `cs campaign packs`. `today` defaults to the UTC
        date: this is a read-only listing, and a one-day boundary difference in
        a listing is immaterial — the SEND gates read the operator's market
        calendar (cs/campaign.py), where it is not."""
        today = today or datetime.now(timezone.utc).date()
        if self.ends_on is not None:
            ends_on = self.ends_on.isoformat()
        elif self.ends_on_declared:
            ends_on = ENDS_ON_NEVER
        else:
            ends_on = None
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "effective_status": self.effective_status(today),
            "delivers": self.delivery_refusal(today) is None,
            "ends_on": ends_on,
            "dates": self.dates,
            "description": self.description,
            "dir": str(self.path),
            "has_builders": self._builders is not None,
        }


def packs_dir(base: str | Path | None = None) -> Path:
    """Where packs live: the clone repo's ``campaigns/`` (cwd-relative — every
    permission string runs from the repo root). ``$CS_CAMPAIGNS_DIR`` overrides
    for sandboxed tests."""
    if base is not None:
        return Path(base)
    return Path(os.environ.get("CS_CAMPAIGNS_DIR") or "campaigns")


def _load_builders(pack_dir: Path):
    p = pack_dir / "builders.py"
    if not p.exists():
        return None
    mod_name = f"cs_campaign_pack_{pack_dir.name.replace('-', '_')}_builders"
    spec = importlib.util.spec_from_file_location(mod_name, p)
    if spec is None or spec.loader is None:  # pragma: no cover - importlib edge
        raise PackError(f"{pack_dir.name}: cannot load builders.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001 — a broken hook must refuse loudly
        raise PackError(f"{pack_dir.name}/builders.py failed to import: {e}") from None
    return mod


def _parse_status(toml_path: Path, meta: dict) -> str:
    """``[pack].status`` — the primary delivery gate, so an unrecognised value
    is a refusal at LOAD, not a silent pass at send time.

    Only an ABSENT key defaults to ``active``: a pack nobody has finished is a
    pack that is running, and every pack written before this gate existed keeps
    working unchanged. A key that is PRESENT is a declaration, so it has to say
    something — an emptied-out status is a half-finished edit, not a campaign
    that is running, and the same rule governs ``ends_on`` below."""
    if "status" not in meta:
        return "active"
    status = str(meta["status"]).strip()
    if status not in STATUSES:
        raise PackError(
            f"{toml_path}: [pack].status must be one of {list(STATUSES)} "
            f"(got {status!r}). It decides whether this campaign may deliver "
            "at all, so an unrecognised word is refused rather than guessed."
        )
    return status


def _parse_ends_on(toml_path: Path, meta: dict) -> tuple[Optional[date], bool]:
    """``[pack].ends_on`` -> (date or None, was it declared).

    Accepts a TOML date literal (``ends_on = 2026-07-31`` — the intended
    shape, validated by the TOML parser itself), the same date as an ISO
    string, or the word ``"never"`` for a campaign with no end. Everything
    else raises: a value that cannot be read as a date must never be read as
    "no limit", which is how a finished campaign keeps delivering.
    """
    if "ends_on" not in meta:
        return None, False
    raw = meta["ends_on"]
    if isinstance(raw, datetime):        # a TOML datetime literal
        return raw.date(), True
    if isinstance(raw, date):            # a TOML date literal
        return raw, True
    if isinstance(raw, str):
        text = raw.strip()
        if text.lower() == ENDS_ON_NEVER:
            return None, True
        try:
            return date.fromisoformat(text), True
        except ValueError:
            pass
    raise PackError(
        f"{toml_path}: [pack].ends_on must be a date (YYYY-MM-DD) or the word "
        f'"{ENDS_ON_NEVER}" for a campaign with no end — got {raw!r}. An '
        "unreadable end date is REFUSED, never read as 'no limit': that is how "
        "a campaign that is over keeps sending. `dates` is the prose field; "
        "this one is the gate."
    )


def load_pack(pack_dir: str | Path) -> Pack:
    pack_dir = Path(pack_dir)
    toml_path = pack_dir / "campaign.toml"
    if not toml_path.exists():
        raise PackError(f"{pack_dir}: no campaign.toml — not a pack")
    try:
        with open(toml_path, "rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise PackError(f"{toml_path} is not valid TOML: {e}") from None
    meta = data.get("pack") or {}
    windows = data.get("windows") or {}
    kind = str(meta.get("kind") or "")
    if kind not in KINDS:
        raise PackError(f"{toml_path}: [pack].kind must be one of {list(KINDS)} (got {kind!r})")
    ends_on, ends_on_declared = _parse_ends_on(toml_path, meta)
    return Pack(
        path=pack_dir,
        name=str(meta.get("campaign") or pack_dir.name),
        kind=kind,
        description=str(meta.get("description") or ""),
        status=_parse_status(toml_path, meta),
        dates=str(meta.get("dates") or ""),
        ends_on=ends_on,
        ends_on_declared=ends_on_declared,
        confirm_question=str(meta.get("confirm_question") or ""),
        reminder_after_hour=windows.get("reminder_after_hour"),
        sms_hour=windows.get("sms_hour"),
        reminder_max=windows.get("reminder_max"),
        _builders=_load_builders(pack_dir),
    )


def list_packs(base: str | Path | None = None) -> list[Pack]:
    root = packs_dir(base)
    if not root.is_dir():
        return []
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if (d / "campaign.toml").exists():
            out.append(load_pack(d))
    return out


def find_pack(campaign_name: str, base: str | Path | None = None) -> Pack | None:
    """Resolve a pack by the ENGINE campaign name (campaign.toml `campaign`,
    defaulting to the directory name). None when no pack matches — the
    campaign handlers turn that into a loud refusal for fixed-template sends."""
    for pack in list_packs(base):
        if pack.name == campaign_name:
            return pack
    return None
