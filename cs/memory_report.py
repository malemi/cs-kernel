"""`cs memory` — the durable stores this operator's knowledge lives in.

WHY THE KERNEL ANSWERS THIS ITSELF. A memory store is a durable body of
records — content that outlives any single run — that at least one kernel
verb or stamped workflow step reads as input. A setting is not a store (it
has a declaring layer and a precedence chain; ``cs config`` answers that
question); a credential or the ``CS_PAUSE`` flag is not a store (no records,
recreatable without loss); a description is not a store when its ground
truth lies elsewhere (the thing it describes wins on disagreement, and the
description is simply wrong). What is left, applied to the running system,
is ten stores.

The map cannot ship as charter prose, because what matters most about each
row — its resolved path, its reachability right now — is per-clone and
per-machine RUNTIME STATE, not a documentable constant: the state directory
depends on the clone's slug, the engine endpoint depends on the manifest,
and the Claude Code memory directory is keyed by an encoded checkout path
that differs per machine. A rendered snapshot of any of it is a claim about
the day it was stamped. So this module resolves the map on THIS machine,
right now, the same shape ``cs config`` already uses for settings: present
or absent, reachable or not, never contents.

Read-only and structurally so: no store write path lives here, and the
engine row's one network action is a connection-level TCP probe — no
WebSocket handshake, no token, no RPC call. Nothing here prints store
contents or PII; the output is safe to paste into a report or a cron
transcript, for the same reason ``cs config`` never prints a secret value.
"""
from __future__ import annotations

import os
import socket
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import campaign_pack, config as config_mod, project_memory

# Connection-level only: long enough that a briefly slow engine host is not
# mistaken for a dead one, short enough that `cs memory` stays fast on a
# machine that cannot reach it at all — the onboarding case this row exists
# for.
ENGINE_PROBE_TIMEOUT_SECONDS = 2.0


def _tilde(p: str | os.PathLike) -> str:
    """`~`-shorten a path under HOME — mirrors `config_report._tilde`."""
    s = str(p)
    home = str(Path.home())
    if s == home:
        return "~"
    return "~" + s[len(home):] if s.startswith(home + os.sep) else s


def _present(path: Path) -> str:
    return "present" if path.exists() else "absent"


# --------------------------------------------------------------- resolvers


def _resolve_engine_memory(settings: Any) -> tuple[str, str]:
    base = (settings.engine_ws_url or "").rstrip("/")
    if not base:
        return "", "unknown: engine_ws_url not configured"
    uid = settings.engine_owner_uid or "<owner_uid>"
    url = f"{base}/ws/{uid}"

    parsed = urllib.parse.urlsplit(base)
    host = parsed.hostname
    if not host:
        return url, "unknown: engine_ws_url not configured"
    port = parsed.port or (443 if parsed.scheme == "wss" else 80)
    try:
        with socket.create_connection((host, port), timeout=ENGINE_PROBE_TIMEOUT_SECONDS):
            return url, "reachable"
    except OSError as e:
        return url, f"unreachable: {e.strerror or e}"


def _resolve_user_notes(settings: Any) -> tuple[str, str]:
    return "RPC: settings.get USER_NOTES", "not probed — needs an authenticated session"


def _resolve_gmail_sent(settings: Any) -> tuple[str, str]:
    ids = [settings.email_address] if settings.email_address else []
    ids += sorted(settings.account_map.keys())
    ids += settings.read_mailbox_list
    location = ", ".join(ids) if ids else "(no mailbox declared)"
    return location, "declared — `cs history` proves readability"


def _resolve_ledger(settings: Any) -> tuple[str, str]:
    p = Path(settings.db_path)
    return _tilde(p), _present(p)


def _resolve_company_notes(settings: Any) -> tuple[str, str]:
    p = Path.cwd() / "company"
    return _tilde(p), _present(p)


def _resolve_dossiers(settings: Any) -> tuple[str, str]:
    p = Path.cwd() / project_memory.PROJECTS_DIR
    return _tilde(p), _present(p)


def _resolve_campaign_packs(settings: Any) -> tuple[str, str]:
    p = Path.cwd() / campaign_pack.packs_dir()
    return _tilde(p), _present(p)


def _resolve_operator_log(settings: Any) -> tuple[str, str]:
    p = Path(settings.log_path)
    return _tilde(p), _present(p)


def _resolve_template_manifest(settings: Any) -> tuple[str, str]:
    p = Path.cwd() / "template-manifest.json"
    return _tilde(p), _present(p)


def _resolve_cc_memory(settings: Any) -> tuple[str, str]:
    # Claude Code's own encoding of a checkout path: both `/` and `.` map to
    # `-` (verified against this machine's `~/.claude/projects/` entries).
    encoded = "".join("-" if c in "/." else c for c in str(Path.cwd()))
    p = Path.home() / ".claude" / "projects" / encoded / "memory"
    return _tilde(p), _present(p)


# ------------------------------------------------------------------- STORES


@dataclass(frozen=True)
class Store:
    id: str
    title: str
    authority: str
    read: str
    write: str
    resolve: Callable[[Any], tuple[str, str]]
    note: str = ""


STORES: tuple[Store, ...] = (
    Store(
        "engine-memory",
        "Engine memory",
        "Entity memory, synced mail, the task ledger, reply and auto-reply "
        "classification, the trained voice. What a message IS. Primary and live.",
        "`cs ask` — empty tool set, cannot write memory",
        "`cs chat --allow create_memory,update_memory` — approval-gated, "
        "denied on the cron in twelve spellings",
        _resolve_engine_memory,
        note="reachable is not authorized — `cs whoami` is the authenticated proof.",
    ),
    Store(
        "user-notes",
        "USER_NOTES (engine profile)",
        "Outreach and reply policy: declared-AI identity, signature, "
        "recipient-language rule, the LLM-ism ban list. The biggest "
        "per-company artifact.",
        "`cs rpc settings.get`",
        "`cs rpc settings.update` — its own six-spelling cron deny block",
        _resolve_user_notes,
    ),
    Store(
        "gmail-sent",
        "Gmail Sent/All Mail",
        "Does this message exist — dedup ground truth, across every "
        "mailbox in scope. Never 'what we know'.",
        "`cs contacted` (one mailbox, one window), `cs history` (every "
        "mailbox, unbounded), the pre-send dedup check — all over IMAP, "
        "none touching the ledger",
        "every real send, including hand-sent mail — which is exactly why "
        "it is the ground truth",
        _resolve_gmail_sent,
    ),
    Store(
        "ledger",
        "SQLite ledger",
        "Its own records only: suppression, the dedup window, and the two "
        "records the mailbox cannot hold — `handled` and `escalated`. "
        "Out-of-band process records that gate sends, not knowledge.",
        "`cs plan`, `cs dossier`, `cs review`, `cs unanswered`, the "
        "campaign runner",
        "`cs handled`, `cs escalated`, `--commit`",
        _resolve_ledger,
    ),
    Store(
        "company-notes",
        "company/*.md",
        "Company facts and any other system this identity may reach.",
        "the files",
        "the operator, via git",
        _resolve_company_notes,
    ),
    Store(
        "dossiers",
        "Dossiers (docs/projects/<name>/)",
        "History and judgement about a project. Secondary — never 'what "
        "we know' on its own.",
        "the files, `/cs-customer`",
        "`cs project new`, then the operator via git",
        _resolve_dossiers,
    ),
    Store(
        "campaign-packs",
        "Campaign packs (campaigns/<pack>/)",
        "What each campaign is, says, and its status and dates — the "
        "record that answers 'have we done something like this?'. "
        "Content only; the runner is kernel code.",
        "`cs campaign packs`, the campaign runner",
        "the operator, via git (copy-and-edit)",
        _resolve_campaign_packs,
    ),
    Store(
        "operator-log",
        "Operator log",
        "What the operator process did and when. Never anything about a "
        "contact.",
        "`cs review` (tail, as evidence), `cs cron status` (last tick)",
        "the cron wrapper, append-only",
        _resolve_operator_log,
    ),
    Store(
        "template-manifest",
        "template-manifest.json",
        "How this clone was built: which kernel template rendered each "
        "stamped file, at which checksum, and the kernel version `cs "
        "init` froze. Never anything about a contact.",
        "`cs update`, to name every stamped file the operator has hand-edited",
        "`cs init`, `cs update`, `cs update --pin`",
        _resolve_template_manifest,
    ),
    Store(
        "cc-memory",
        "Claude Code memory",
        "Nothing that leaves this desk. Working style and per-developer "
        "preference only. Per-user, per-machine, not in git, not portable.",
        "injected into every session's context — which is exactly why it "
        "must be governed",
        "the local agent",
        _resolve_cc_memory,
    ),
)


# ------------------------------------------------------------------ the report


def build(settings: Any = None) -> dict:
    """The whole report as data — what `render()` prints and `--json` emits."""
    settings = settings if settings is not None else config_mod.load()
    stores = []
    for s in STORES:
        location, presence = s.resolve(settings)
        stores.append(
            {
                "id": s.id,
                "title": s.title,
                "authority": s.authority,
                "read": s.read,
                "write": s.write,
                "location": location,
                "presence": presence,
                "note": s.note,
            }
        )
    return {"stores": stores}


def render(rep: dict) -> str:
    """The human- and agent-readable report — every line safe to paste into a
    report or a cron transcript."""
    out: list[str] = []
    add = out.append

    add("cs memory — the durable stores this operator's knowledge lives in, "
        "one per row.")
    add("A store is a body of records at least one verb or workflow step "
        "reads as input;")
    add("a setting, a credential, or a description is not one — see "
        "`cs config` for settings.")

    for i, s in enumerate(rep["stores"], 1):
        add("")
        add(f"{i:>2}. {s['title']}  [{s['id']}]")
        add(f"    authoritative for: {s['authority']}")
        add(f"    read:     {s['read']}")
        add(f"    write:    {s['write']}")
        add(f"    location: {s['location'] or '(none)'}")
        add(f"    status:   {s['presence']}")
        if s["note"]:
            add(f"    note:     {s['note']}")

    return "\n".join(out)
