"""Exact interactive-reply successors to the reviewed scheduled template bytes.

The scheduled-surface comparison in test_capabilities_skill.py binds the
current scheduled sources to separately reviewed byte hashes. The interactive
reply workflow text (ported from the reviewed M5 workflow sources), the
interactive `draft-retire` ask rule and the raw-RPC denies of the engine's exact
send, retirement and publication operations change four of those sources. This module
reverses exactly those recorded edits, and nothing else, so the older binding
can still be checked byte for byte. Every stage is bound by its postimage and
preimage SHA-256; an edit must occur exactly once. Any other difference fails.

The manifest records `review_state`; it does not claim a review that has not
happened. The stage bytes still need a fresh review of the scheduled surfaces.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("scheduled_m5_successor.json")
REVIEW_STATE = "PENDING_FRESH_REVIEW"
STAGES = (
    ("m5-interactive-reply-triage", "cs/templates/project/.claude/skills/cs-triage-mail/SKILL.md.j2"),
    ("m5-shared-partial", "cs/templates/partials/outbound-fact-sourcing.md.j2"),
    ("interactive-reply-permissions", "cs/templates/project/.claude/settings.json.j2"),
    ("interactive-reply-raw-rpc-denies", "cs/templates/project/bin/cs_operator_cron.sh.j2"),
)
SELECTED_READ_STAGES = tuple(
    ("scheduled-selected-reads-" + skill, f"cs/templates/project/.claude/skills/{skill}/SKILL.md.j2")
    for skill in ("cs-triage-mail", "cs-campaign-tick")
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def load(packet=None, expected_stages=STAGES):
    """Validate the manifest shape and return its stages keyed by template path."""
    if packet is None:
        packet = json.loads(MANIFEST.read_text())
    assert isinstance(packet, dict) and set(packet) == {"schema_version", "review_state", "origin", "stages"}, \
        "invalid successor manifest"
    assert packet["schema_version"] == 1, "unknown successor schema"
    assert packet["review_state"] == REVIEW_STATE, "successor review state changed"
    stages = packet["stages"]
    assert isinstance(stages, list) and len(stages) == len(expected_stages), "wrong successor stage cardinality"
    result = {}
    for stage, (identity, template) in zip(stages, expected_stages):
        assert isinstance(stage, dict) and set(stage) == {"id", "template", "hashes", "edits"}, \
            "missing or extra stage field"
        assert stage["id"] == identity and stage["template"] == template, "wrong stage binding"
        hashes = stage["hashes"]
        assert isinstance(hashes, dict) and set(hashes) == {"before_sha256", "after_sha256"}, \
            "missing or extra stage hash"
        assert all(_hash(v) for v in hashes.values()), "invalid stage hash"
        edits = stage["edits"]
        assert isinstance(edits, list) and edits, "stage has no edits"
        for edit in edits:
            assert isinstance(edit, dict) and set(edit) == {"before", "after"}, "invalid edit"
            assert isinstance(edit["before"], str) and isinstance(edit["after"], str) and edit["after"], \
                "invalid edit bytes"
        result[template] = stage
    return result


def undo_stage(template, data, stages):
    if template not in stages:
        return data
    stage = stages[template]
    assert digest(data) == stage["hashes"]["after_sha256"], f"successor postimage mismatch: {template}"
    for edit in reversed(stage["edits"]):
        after, before = edit["after"].encode(), edit["before"].encode()
        assert data.count(after) == 1, f"successor edit must occur exactly once: {template}"
        data = data.replace(after, before, 1)
    assert digest(data) == stage["hashes"]["before_sha256"], f"successor preimage mismatch: {template}"
    return data


def undo(template, data, packet=None):
    """Reverse selected-read guidance before the earlier interactive-reply stage."""
    selected = json.loads((MANIFEST.parent / "fixtures/selected-read-guidance.json").read_text())
    data = undo_stage(template, data, load(selected, SELECTED_READ_STAGES))
    return undo_stage(template, data, load(packet))


def undo_template(rel, data, packet=None):
    """`rel` is relative to cs/templates/project, as test_capabilities_skill names it."""
    return undo("cs/templates/project/" + rel + ".j2", data, packet)
