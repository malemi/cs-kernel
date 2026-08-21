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
"""
from __future__ import annotations

import importlib.util
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

KINDS = ("fixed-template", "composed-draft")


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
    status: str = "active"    # active | done
    dates: str = ""           # prose: when it ran
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

    def summary(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
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
    return Pack(
        path=pack_dir,
        name=str(meta.get("campaign") or pack_dir.name),
        kind=kind,
        description=str(meta.get("description") or ""),
        status=str(meta.get("status") or "active"),
        dates=str(meta.get("dates") or ""),
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
