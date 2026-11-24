"""Read protected enrollments for exact operational-test original messages."""
from __future__ import annotations

import email
import hashlib
import imaplib
import json
import math
import os
import re
import stat
from pathlib import Path
from email import policy
from email.utils import getaddresses
from time import time, monotonic

from . import observability_causal as causal
from . import observability_producers as diagnostics

REGISTRY_ROOT = Path("/etc/cs-operator-fixtures")
MAX_BYTES = 32768
MAX_LIFETIME = 5400
MAX_MIME_BYTES = 262144


def _diagnostic(settings, check, cause, *, phase=None, outcome="failed", started=None, error=None, **facts):
    try:
        if started is not None:
            facts["elapsed_ms"] = int(max(0, monotonic() - started) * 1000)
        method = "fixture." + (phase or "admission")
        value = causal.decision(check, cause, layer="source", phase="discovery",
                                command="unanswered", method=method, outcome=outcome, **facts)
        metadata = diagnostics.error_metadata(error) if error is not None else {}
        status = "start" if cause == "provider_started" else "failed" if outcome == "failed" else "held" if outcome == "held" else "result"
        diagnostics.emit(settings, "discovery", status,
                         reason=diagnostics.error_reason(error) if error is not None else "none",
                         method=method, causal=value, **({"level": "DEBUG"} if cause == "registry_absent" else {}), **metadata)
    except Exception:
        pass


def _protected(st, directory=False):
    return (st.st_uid == 0 and not st.st_mode & 0o022
            and (stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)))


def _read(path, settings=None):
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        if not _protected(os.fstat(directory), True):
            _diagnostic(settings, "fixture_registry", "registry_invalid")
            return None
        for part in path.parts[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=directory)
            os.close(directory)
            directory = nxt
            if not _protected(os.fstat(directory), True):
                _diagnostic(settings, "fixture_registry", "registry_invalid")
                return None
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not _protected(before) or before.st_size > MAX_BYTES:
                _diagnostic(settings, "fixture_registry", "registry_invalid")
                return None
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            if len(raw) > MAX_BYTES or (before.st_size, before.st_mtime_ns) != (
                    after.st_size, after.st_mtime_ns):
                _diagnostic(settings, "fixture_registry", "registry_invalid")
                return None
            return json.loads(raw, object_pairs_hook=_unique)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        absent = isinstance(exc, FileNotFoundError)
        _diagnostic(settings, "fixture_registry", "registry_absent" if absent else "registry_invalid",
                    outcome="accepted" if absent else "failed", error=exc)
        return None
    finally:
        os.close(directory)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate registry field")
        result[key] = value
    return result


def _text(value, maximum=254):
    return isinstance(value, str) and 0 < len(value) <= maximum and not any(
        ord(char) < 32 or ord(char) == 127 for char in value)


def _timestamp(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def enrollments(settings, now=None):
    def reject():
        _diagnostic(settings, "fixture_registry", "registry_invalid")
        return []

    uid = getattr(settings, "engine_owner_uid", "")
    receiver = (getattr(settings, "email_address", "") or "").strip().lower()
    mode = getattr(settings, "cs_triage_mode", "")
    if not isinstance(uid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uid):
        return reject()
    if mode not in {"send", "draft"} or not _text(receiver):
        return reject()
    payload = _read(REGISTRY_ROOT / (uid + ".json"), settings)
    if payload is None:
        return []
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        return reject()
    identity = {"owner_uid": uid, "receiver": receiver, "mode": mode}
    if any(payload.get(key) != value for key, value in identity.items()):
        return reject()
    rows = payload.get("fixtures")
    if not isinstance(rows, list) or len(rows) > 16:
        return reject()
    clock = time() if now is None else now
    accepted = []
    seen = set()
    nonces = set()
    for row in rows:
        if not isinstance(row, dict) or any(row.get(k) != v for k, v in identity.items()):
            return reject()
        if any(not _text(row.get(k)) for k in ("sender", "message_id", "subject", "nonce")):
            return reject()
        sender, mid, nonce = row["sender"], row["message_id"], row["nonce"]
        if (sender != sender.lower() or sender == receiver or "@" not in sender
                or not re.fullmatch(r"<[^<>\s]+@[^<>\s]+>", mid)
                or not re.fullmatch(r"[a-f0-9]{32,64}", nonce)
                or nonce not in row["subject"]
                or not isinstance(row.get("body_sha256"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", row["body_sha256"])):
            return reject()
        created, expires = row.get("created_at"), row.get("expires_at")
        if (not _timestamp(created) or not _timestamp(expires)
                or not 0 < expires - created <= MAX_LIFETIME or created > clock):
            return reject()
        receipt = row.get("provider_receipt")
        if not isinstance(receipt, dict) or any(receipt.get(k) != row[k] for k in (
                "sender", "receiver", "message_id", "subject", "body_sha256")):
            return reject()
        if (not _text(receipt.get("folder")) or any(
                not isinstance(receipt.get(k), str) or not re.fullmatch(r"[1-9][0-9]{0,19}", receipt[k])
                for k in ("uid", "uidvalidity")) or mid in seen or nonce in nonces):
            return reject()
        seen.add(mid)
        nonces.add(nonce)
        if clock < expires:
            accepted.append(row)
    _diagnostic(settings, "fixture_registry", "registry_expired" if len(accepted) < len(rows) else "registry_valid",
                outcome="held" if len(accepted) < len(rows) else "accepted",
                enrollment_count=len(accepted), expired_count=len(rows) - len(accepted))
    return accepted


def _binding_failure(message, row):
    receipt = row["provider_receipt"]
    predicates = (
        ("binding_sender", lambda: (message.get("email") or "").strip().lower() == row["sender"]),
        ("binding_message", lambda: message.get("message_id") == row["message_id"]),
        ("binding_subject", lambda: str(message.get("subject") or "") == row["subject"]),
        ("binding_thread", lambda: message.get("thread_key") == row["message_id"]),
        *(("binding_" + key, lambda key=key: message.get("provider_" + key) == receipt[key])
          for key in ("folder", "uid", "uidvalidity")),
    )
    return next((name for name, predicate in predicates if not predicate()), None)


def _matches(message, row):
    return _binding_failure(message, row) is None


def _original_digest(raw, row):
    message = email.message_from_bytes(raw, policy=policy.default)
    if message.is_multipart() or message.get_content_type() != "text/plain":
        return False
    if message.get_content_disposition() == "attachment" or message.get_filename():
        return False
    if any(len(message.get_all(key, [])) != 1 for key in ("From", "To", "Message-ID", "Subject")):
        return False
    if message.get("References") or message.get("In-Reply-To") or message.get("Cc") or message.get("Bcc"):
        return False
    sender = getaddresses(message.get_all("From", []))
    receiver = getaddresses(message.get_all("To", []))
    if (len(sender) != 1 or sender[0][1].lower() != row["sender"]
            or len(receiver) != 1 or receiver[0][1].lower() != row["receiver"]
            or str(message.get("Message-ID")).strip() != row["message_id"]
            or str(message.get("Subject")) != row["subject"]):
        return False
    body = message.get_content().replace("\r\n", "\n").rstrip("\n")
    digest = hashlib.sha256(body.encode()).hexdigest()
    return digest if digest == row["body_sha256"] else False


def _provider_original(client, row, settings=None):
    phase = "select"
    started = monotonic()

    def mark(selected, cause="provider_passed", outcome="accepted", error=None):
        _diagnostic(settings, "fixture_provider", cause, phase=selected, outcome=outcome, started=started, error=error)

    def reject():
        mark(phase, "provider_rejected", "failed")
        return False
    try:
        receipt = row["provider_receipt"]
        folder = receipt["folder"]
        if any(char in folder for char in '\"\\\r\n'):
            return reject()
        mark(phase, "provider_started")
        typ, _ = client.select('"' + folder + '"', readonly=True)
        if typ != "OK":
            return reject()
        mark(phase)
        phase = "uidvalidity"
        started = monotonic()
        mark(phase, "provider_started")
        typ, validity = client.response("UIDVALIDITY")
        if not typ or not validity or not validity[0]:
            return reject()
        observed = validity[0].decode() if isinstance(validity[0], bytes) else str(validity[0])
        if observed != receipt["uidvalidity"]:
            return reject()
        mark(phase)
        phase = "fetch"
        started = monotonic()
        mark(phase, "provider_started")
        typ, parts = client.uid("FETCH", receipt["uid"],
                                f"(UID FLAGS RFC822.SIZE BODY.PEEK[]<0.{MAX_MIME_BYTES}>)")
        literals = [part for part in (parts or []) if isinstance(part, tuple)] if typ == "OK" else []
        if len(literals) != 1:
            return reject()
        meta, raw = literals[0]
        if not isinstance(meta, bytes) or not isinstance(raw, bytes) or len(raw) >= MAX_MIME_BYTES:
            return reject()
        uid = re.search(rb"\bUID\s+(\d+)\b", meta, re.I)
        size = re.search(rb"\bRFC822.SIZE\s+(\d+)\b", meta, re.I)
        if (not uid or uid[1].decode() != receipt["uid"] or not size
                or int(size[1]) != len(raw) or b"\\Draft" in meta):
            return reject()
        mark(phase)
        phase = "mime"
        started = monotonic()
        mark(phase, "provider_started")
        digest = _original_digest(raw, row)
        mark(phase, "provider_passed" if digest else "provider_rejected", "accepted" if digest else "failed")
        return digest

    except BaseException as exc:
        mark(phase, "provider_exception", "failed", exc)
        raise


def _confirmed(settings, rows):
    if not rows:
        return []
    client = None
    phase = "connect"
    started = monotonic()
    try:
        _diagnostic(settings, "fixture_provider", "provider_started", phase=phase, outcome="accepted", started=started)
        client = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port, timeout=15)
        _diagnostic(settings, "fixture_provider", "provider_passed", phase=phase, outcome="accepted", started=started)
        phase = "login"
        started = monotonic()
        _diagnostic(settings, "fixture_provider", "provider_started", phase=phase, outcome="accepted", started=started)
        client.login(settings.email_address, (settings.email_password or "").replace(" ", "").strip())
        _diagnostic(settings, "fixture_provider", "provider_passed", phase=phase, outcome="accepted", started=started)
        phase = None
        confirmed = []
        for row in rows:
            digest = _provider_original(client, row, settings)
            if digest:
                confirmed.append({**row, "_verified_body_sha256": digest})
        return confirmed
    except (OSError, imaplib.IMAP4.error, ValueError, TypeError, AttributeError, LookupError) as exc:
        if phase is not None:
            _diagnostic(settings, "fixture_provider", "provider_exception", phase=phase, started=started, error=exc)
        return []
    finally:
        if client is not None:
            started = monotonic()
            try:
                client.logout()
                _diagnostic(settings, "fixture_provider", "provider_passed", phase="logout", outcome="accepted", started=started)
            except (OSError, imaplib.IMAP4.error) as exc:
                _diagnostic(settings, "fixture_provider", "provider_exception", phase="logout", started=started, error=exc)


def admit_originals(settings, inbound, self_addrs, now=None, discovery=None):
    effective_self = {a.strip().lower() for a in self_addrs if a}
    rows = enrollments(settings, now)
    candidates = []
    matches = 0
    for row in rows:
        failures = [_binding_failure(message, row) for message in inbound]
        count = sum(failure is None for failure in failures)
        matches += count
        if count == 1:
            candidates.append(row)
        else:
            failure = "source_duplicate" if count > 1 else next(
                (failure for message, failure in zip(inbound, failures)
                 if message.get("message_id") == row["message_id"]), "source_absent")
            _diagnostic(settings, "fixture_binding", failure, observed=count)
    _diagnostic(settings, "fixture_admission", "candidates_selected", outcome="accepted",
                inbound_count=len(inbound), enrollment_count=len(rows), match_count=matches, candidate_count=len(candidates))
    originals = _confirmed(settings, candidates)
    _diagnostic(settings, "fixture_admission", "confirmation_complete", outcome="accepted",
                inbound_count=len(inbound), enrollment_count=len(rows), match_count=matches,
                candidate_count=len(candidates), confirmed_count=len(originals))
    kept, admitted = [], set()
    for message in inbound:
        sender = (message.get("email") or "").strip().lower()
        original = next((row for row in originals if _matches(message, row)), None)
        if sender not in effective_self:
            kept.append(message)
        else:
            if original is None:
                continue
            kept.append(message)
            admitted.add(sender)
        if original is not None and discovery is not None:
            discovery.append({"message_id": str(message["message_id"]),
                              "provider_folder": message["provider_folder"],
                              "provider_uid": message["provider_uid"],
                              "provider_uidvalidity": message["provider_uidvalidity"],
                              "owner_uid": settings.engine_owner_uid,
                              "body_sha256": original["_verified_body_sha256"]})
    return kept, effective_self - admitted


def discovered_roots(settings, discovery):
    if not isinstance(discovery, list) or not discovery or len(discovery) > 16:
        return set()
    expected = {}
    for row in enrollments(settings):
        receipt = row["provider_receipt"]
        expected[row["message_id"]] = {
            "message_id": row["message_id"], "owner_uid": row["owner_uid"],
            "body_sha256": row["body_sha256"],
            **{"provider_" + key: receipt[key] for key in ("folder", "uid", "uidvalidity")},
        }
    roots = set()
    for row in discovery:
        if not isinstance(row, dict) or not isinstance(row.get("message_id"), str):
            return set()
        root = row["message_id"]
        if root in roots or row != expected.get(root):
            return set()
        roots.add(root)
    return roots
