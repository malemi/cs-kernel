#!/usr/bin/env python3
"""Deterministic bootstrap contract, upgrade and scheduled-surface checks.

These checks establish what the rendered instructions say and what real stamping
preserves. Native host acceptance separately proves agent selection and behavior.
The comparison base is the reviewed legal-skill tip preceding this bootstrap.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cs import project_init as pi
from test_project_update import _FULL_INIT_DATA

BASE_COMMIT = "03b4449"
TPL = ROOT / "cs/templates/project"
SKILL_REL = ".claude/skills/cs-bootstrap/SKILL.md"
SCHEDULED = (
    ".claude/settings.json", "bin/cs_operator_cron.sh",
    ".claude/skills/cs-operator/SKILL.md",
    ".claude/skills/cs-triage-mail/SKILL.md",
    ".claude/skills/cs-campaign-tick/SKILL.md",
)
FAILED = 0
WORKSET_RENDERED = {}
RELEASE_RENDERED = {}
RELEASE_REVIEW = json.loads((ROOT / "tests/fixtures/reviewed-release-scheduled-surfaces.json").read_text())


def executor_guidance_binding():
    record = json.loads((ROOT / "tests/fixtures/executor-guidance-binding.json").read_text())
    assert record["baseline_commit"] == "d1dbe36348543cd736167fe32796f5bb55d38271"
    assert record["review_state"] == "REVISE_PENDING_REQUIRED_EVIDENCE"
    receipt = (ROOT / "tests/fixtures" / record["checkpoint_receipt"]).read_bytes()
    assert hashlib.sha256(receipt).hexdigest() == record["checkpoint_receipt_sha256"]
    assert b"- Verdict: REVISE\n" in receipt
    assert set(record["templates"]) == {
        ".claude/skills/cs-operator/SKILL.md", ".claude/skills/cs-triage-mail/SKILL.md",
        ".claude/skills/cs-campaign-tick/SKILL.md", "bin/cs_operator_cron.sh"}
    assert set(record["partials"]) == {"cs/templates/partials/operator-executor-tools.md.j2"}
    for path, digest in record["partials"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    return record


def undo_executor_guidance(rel: str, text: bytes) -> bytes:
    record = executor_guidance_binding()
    if rel not in record["templates"]:
        return text
    binding = record["templates"][rel]
    assert hashlib.sha256(text).hexdigest() == binding["after_sha256"]
    for edit in reversed(binding["edits"]):
        start, end = edit["after_start"], edit["after_end"]
        assert 0 <= start <= end <= len(text)
        assert text[start:end] == edit["after"].encode()
        text = text[:start] + edit["before"].encode() + text[end:]
    assert hashlib.sha256(text).hexdigest() == binding["before_sha256"]
    return text


def undo_subskill_timeout_guidance(rel: str, text: bytes) -> bytes:
    record = json.loads((ROOT / "tests/fixtures/reviewed-subskill-timeout-guidance.json").read_text())
    if rel not in record["templates"]:
        return text
    receipt = (ROOT / "tests/fixtures" / record["receipt"]).read_bytes()
    assert hashlib.sha256(receipt).hexdigest() == record["receipt_sha256"]
    binding = record["templates"][rel]
    assert hashlib.sha256(text).hexdigest() == binding["after_sha256"]
    assert text.count(b"timeout: 2730000") == binding["count"]
    assert b"timeout: 600000" not in text
    prior = text.replace(b"timeout: 2730000", b"timeout: 600000")
    assert hashlib.sha256(prior).hexdigest() == binding["before_sha256"]
    return prior



def undo_parent_send_guidance(text: bytes) -> bytes:
    record = json.loads((ROOT / "tests/fixtures/reviewed-parent-send-guidance.json").read_text())
    receipt = (ROOT / "tests/fixtures" / record["plan_review_receipt"]).read_bytes()
    assert hashlib.sha256(receipt).hexdigest() == record["plan_review_sha256"]
    assert hashlib.sha256(text).hexdigest() == record["after_sha256"]
    for edit in reversed(record["edits"]):
        before, after = edit["before"].encode(), edit["after"].encode()
        assert text.count(after) == 1
        text = text.replace(after, before, 1)
    assert hashlib.sha256(text).hexdigest() == record["before_sha256"]
    return text


def undo_e18_operator_guidance(text: bytes) -> bytes:
    record = json.loads((ROOT / "tests/fixtures/reviewed-e18-operator-guidance.json").read_text())
    receipt = (ROOT / "tests/fixtures" / record["plan_review_receipt"]).read_bytes()
    assert hashlib.sha256(receipt).hexdigest() == record["plan_review_sha256"]
    before, after = record["before"].encode(), record["after"].encode()
    assert text.count(after) == 1
    assert before not in text
    return text.replace(after, before, 1)


def prior_workset_template(rel: str) -> str | None:
    """Reverse only the exact separately reviewed workset template hunks.

    Keep the older bootstrap's byte comparison and mutation negatives intact;
    this candidate intentionally changes its two scheduled mail workflows.
    """
    records = json.loads((ROOT / 'tests/fixtures/reviewed-workset-guidance.json').read_text())
    if rel not in records:
        return None
    record = records[rel]
    text = undo_executor_guidance(rel, (TPL / (rel + '.j2')).read_bytes()).decode()
    if rel == '.claude/skills/cs-operator/SKILL.md':
        text = undo_e18_operator_guidance(undo_parent_send_guidance(text.encode())).decode()
    framing = json.loads((ROOT / 'tests/fixtures/reviewed-inventory-eof-guidance.json').read_text())
    if rel in framing:
        addition = framing[rel]
        assert hashlib.sha256(text.encode()).hexdigest() == addition['after_sha256']
        for edit in addition['edits']:
            assert text.count(edit['after']) == 1
            text = text.replace(edit['after'], edit['before'], 1)
        assert hashlib.sha256(text.encode()).hexdigest() == addition['before_sha256']
    semantic = json.loads((ROOT / 'tests/fixtures/reviewed-semantic-inventory-guidance.json').read_text())
    if rel in semantic:
        addition = semantic[rel]
        assert hashlib.sha256(text.encode()).hexdigest() == addition['after_sha256']
        for edit in addition['edits']:
            assert text.count(edit['after']) == 1
            text = text.replace(edit['after'], edit['before'], 1)
        assert hashlib.sha256(text.encode()).hexdigest() == addition['before_sha256']
    # Keep the immutable historical workset ledger: reverse only the exact
    # separately reviewed native-read guidance before its byte comparison.
    additions = json.loads((ROOT / 'tests/fixtures/reviewed-native-read-guidance.json').read_text())
    if rel in additions:
        addition = additions[rel]
        assert hashlib.sha256(text.encode()).hexdigest() == addition['after_sha256']
        for edit in addition['edits']:
            assert text.count(edit['after']) == 1
            text = text.replace(edit['after'], edit['before'], 1)
        assert hashlib.sha256(text.encode()).hexdigest() == addition['before_sha256']
    assert hashlib.sha256(text.encode()).hexdigest() == record['after_sha256']
    for edit in record['edits']:
        assert text.count(edit['after']) == 1
        text = text.replace(edit['after'], edit['before'], 1)
    assert hashlib.sha256(text.encode()).hexdigest() == record['before_sha256']
    return text

EXACT_DRAFT_DENIES = {
    f"Bash({spelling} {verb}:*)"
    for spelling in (".venv/bin/python -m cs", ".venv/bin/python3 -m cs", ".venv/bin/cs",
                     "python -m cs", "python3 -m cs", "cs")
    for verb in ("draft-retire", "rpc drafts.discard_exact", "rpc drafts.reconcile_external")
}


REVIEWED_DISCOVERY_GUIDANCE = {'standalone': '78921f670f94482dc9ecb85e6a1dba380cf4dfb644101eabd01697f793565f32', 'private_discovery': '8e301e08251b554c36a075c33baa6be1d5c84db57fe1f5827985673d68a201b7', 'global_pending': '24fbc5ff80cf1dd53e8ebe63c8de5524c786e6b613a2f332a410d209f0e30026'}


REVIEWED_AUTHORITY_GUIDANCE = {'paragraph': '683a0037560809a54eaa2b9a3dc473b252accbbd5254a400ae85494279b261dd', 'cs-operator': ['- **Assignment holds survive this bootstrap.** The common sweep and exact-thread\n  assignment projection decide the boundary before Sent subtraction or drafting.', '- **Current assignment holds survive this bootstrap.** The current exact-thread\n  assignment projection decides the boundary before Sent subtraction or drafting;\n  only an earlier transient UNKNOWN snapshot may be superseded under the current\n  authority rule above.'], 'cs-triage-mail': ["- With complete scope and no assignment hold, use the common sweep's result\n  for this conversation. Do not turn an arbitrary later Sent row into an", "- With complete scope and no assignment hold in the current exact-thread\n  projection, apply the current authority rule above for eligibility and the\n  common sweep's reply-kind judgement for this conversation. Do not turn an arbitrary later Sent row into an"]}


def undo_reviewed_discovery_guidance(rel: str, after: bytes) -> bytes | None:
    """Reverse only the exact reviewed M2 additions before the M6 comparison."""
    authority_skills = {".claude/skills/cs-operator/SKILL.md": "cs-operator",
                        ".claude/skills/cs-triage-mail/SKILL.md": "cs-triage-mail"}
    if rel in authority_skills:
        ordinary_start = (b"### Ordinary discovery transport and health\n" if authority_skills[rel] == "cs-operator"
                          else b"\n### Ordinary discovery transport and health\n")
        ordinary_end = (b"## Protected operational originals\n" if authority_skills[rel] == "cs-operator"
                        else b"This skill is **general**")
        if after.count(ordinary_start) != 1 or after.count(ordinary_end) != 1:
            return None
        first = after.index(ordinary_start)
        last = after.index(ordinary_end, first)
        ordinary_hashes = {'cs-operator': '42d87084fb13482ba141d4670733a8345aad43ec9604e901b5109f2ac7a59140', 'cs-triage-mail': '4156e448687f0631a27feede47a593f3dd86bc72bfe02a25df11696809da884e'}
        if hashlib.sha256(after[first:last]).hexdigest() != ordinary_hashes[authority_skills[rel]]:
            return None
        after = after[:first] + after[last:]
        if authority_skills[rel] == "cs-triage-mail":
            ordinary_pairs = (
                (b"Use the ordinary artifact protocol above when its path is supplied.",
                 b"If an ordinary output file exists, use normal Read calls through its end."),
                (b"If no ordinary artifact was supplied, a protected run may locate only its existing receipt path:",
                 b"For clipped output in a protected run, locate only the existing receipt path:"),
            )
            for current, prior in ordinary_pairs:
                if after.count(current) != 1:
                    return None
                after = after.replace(current, prior, 1)
        start = b"### Current authority after a transient UNKNOWN snapshot\n"
        end = (b"## 0. The invariant" if authority_skills[rel] == "cs-operator"
               else b"## Invariants (read before acting)")
        if after.count(start) != 1 or after.count(end) != 1:
            return None
        first, last = after.index(start), after.index(end)
        if hashlib.sha256(after[first:last]).hexdigest() != REVIEWED_AUTHORITY_GUIDANCE["paragraph"]:
            return None
        after = after[:first] + after[last:]
        old, new = REVIEWED_AUTHORITY_GUIDANCE[authority_skills[rel]]
        if after.count(new.encode()) != 1:
            return None
        after = after.replace(new.encode(), old.encode(), 1)
    skills = {".claude/skills/cs-operator/SKILL.md",
              ".claude/skills/cs-triage-mail/SKILL.md",
              ".claude/skills/cs-campaign-tick/SKILL.md"}
    if rel == ".claude/skills/cs-operator/SKILL.md":
        tasks_start = b"## 2c. Read the primary account tasks before triage\n"
        tasks_end = b"## 3. Recurring job"
        if tasks_start in after:
            if after.count(tasks_start) != 1 or after.count(tasks_end) != 1:
                return None
            first, last = after.index(tasks_start), after.index(tasks_end)
            if hashlib.sha256(after[first:last]).hexdigest() != "b039396203f9c76594125dbc010bc0005d2349e6341e23ea251f01f68b83e179":
                return None
            after = after[:first] + after[last:]
    start = b"Run each `cs` command below in its own native Bash tool call."
    if rel not in skills or start not in after:
        return after
    if after.count(start) != 1:
        return None
    anchor = "All commands run from the repo root with `.venv/bin/python -m cs …`.\n".encode()
    if after.count(anchor) != 1:
        return None
    first = after.index(start)
    if first != after.index(anchor) + len(anchor) + 1:
        return None
    last = after.find(b"\n\n", first)
    if last < 0 or hashlib.sha256(after[first:last + 1]).hexdigest() != REVIEWED_DISCOVERY_GUIDANCE["standalone"]:
        return None
    after = after[:first - 1] + after[last + 1:]
    if rel == ".claude/skills/cs-triage-mail/SKILL.md":
        start = b"### Complete discovery inspection\n"
        end = b"## Protected operational originals before ordinary queue order"
        if after.count(start) != 1 or after.count(end) != 1:
            return None
        first, last = after.index(start), after.index(end)
        if hashlib.sha256(after[first:last]).hexdigest() != REVIEWED_DISCOVERY_GUIDANCE["private_discovery"]:
            return None
        after = after[:first] + after[last:]
        pairs = [
            (b".venv/bin/python -m cs unanswered --days 14 --json --all-buckets", b".venv/bin/python -m cs tasks --json"),
            (b".venv/bin/python -m cs assignment status '<exact-thread-key>' --json", b".venv/bin/python -m cs dossier <email>"),
            (b".venv/bin/python -m cs dossier <email>", b".venv/bin/python -m cs contacted <email>"),
            (b".venv/bin/python -m cs contacted <email>", b".venv/bin/python -m cs history <email>"),
            (b".venv/bin/python -m cs tasks --json", b".venv/bin/python -m cs rpc tasks.list '{\"include_completed\":true}'"),
        ]
        for a, b in pairs:
            separated = a + b"\n```\n\n```bash\n" + b
            if after.count(separated) != 1:
                return None
            after = after.replace(separated, a + b"\n" + b, 1)
    if rel == ".claude/skills/cs-campaign-tick/SKILL.md":
        heading = b"## 2. Pull each campaign's worklist\n"
        end = b"it does not replace this global inventory or widen an exclusion or send gate.\n"
        if after.count(heading) != 1 or after.count(end) != 1:
            return None
        first, last = after.index(heading) + len(heading), after.index(end) + len(end)
        if hashlib.sha256(after[first:last]).hexdigest() != REVIEWED_DISCOVERY_GUIDANCE["global_pending"]:
            return None
        return after[:first] + after[last:]
    marker = b".venv/bin/python -m cs review --json\n```\n\n`drafts[]` contains one row per logical draft.\n"
    if after.count(marker) != 1:
        return None
    original = ".venv/bin/python -m cs review --json     # drafts[] — one row per logical draft\n```\n".encode()
    after = after.replace(marker, original, 1)
    if rel == ".claude/skills/cs-operator/SKILL.md":
        tasks = re.findall(rb"(?m)^\.venv/bin/python -m cs --account [^\n]+ tasks$", after)
        if tasks:
            if len(tasks) != 1:
                return None
            separated = tasks[0] + b"\n```\n\n```bash\n.venv/bin/python -m cs --account "
            if after.count(separated) != 1:
                return None
            after = after.replace(separated, tasks[0] + b"\n.venv/bin/python -m cs --account ", 1)
    return after


def preserves_scheduled_contract(rel: str, before: bytes, after: bytes) -> bool:
    """Only independently reviewed exact additions may differ."""
    if (rel, after) in RELEASE_RENDERED:
        return RELEASE_RENDERED[(rel, after)] == before
    if rel == ".claude/skills/cs-operator/SKILL.md":
        try:
            after = undo_e18_operator_guidance(after)
        except AssertionError:
            return False
    after = WORKSET_RENDERED.get((rel, after), after)
    after = undo_reviewed_discovery_guidance(rel, after)
    if after is None:
        return False
    additions = {
        ".claude/skills/cs-operator/SKILL.md": (
            b"## Protected operational originals\n", b"## 0. The invariant",
            "d2b8ff54dd33f456ff0324ad9d887602aea367b327199026f4d8fb8088e6bbdf"),
        ".claude/skills/cs-triage-mail/SKILL.md": (
            b"## Protected operational originals before ordinary queue order\n",
            b"## Invariants (read before acting)",
            "0a6182efe81e17ecb5153a1b25866bf523acc7bcb31fbb84b6ab43ffb57840ee"),
    }
    if rel in additions:
        start, end, approved = additions[rel]
        if after.count(start) != 1 or after.count(end) != 1:
            return False
        first, last = after.index(start), after.index(end)
        if hashlib.sha256(after[first:last]).hexdigest() != approved:
            return False
        return after[:first] + after[last:] == before
    if rel == ".claude/settings.json":
        old, new = json.loads(before), json.loads(after)
        deny = new["permissions"]["deny"]
        if any(deny.count(token) != 1 for token in EXACT_DRAFT_DENIES):
            return False
        new["permissions"]["deny"] = [token for token in deny if token not in EXACT_DRAFT_DENIES]
        return old == new
    if rel == "bin/cs_operator_cron.sh":
        kept = []
        observed = []
        for line in after.decode().splitlines(keepends=True):
            token = line.strip().removesuffix("\\").strip().strip('"')
            if token in EXACT_DRAFT_DENIES:
                observed.append(token)
            else:
                kept.append(line)
        return (set(observed) == EXACT_DRAFT_DENIES and len(observed) == len(EXACT_DRAFT_DENIES)
                and "".join(kept).encode() == before)
    return before == after


def check(label: str, condition: bool) -> None:
    global FAILED
    print(f"  {'ok  ' if condition else 'FAIL'} {label}")
    FAILED += not condition


def normalized(text: str) -> str:
    return " ".join(text.lower().split())


def contains(text: str, *clauses: str) -> bool:
    return all(normalized(clause) in normalized(text) for clause in clauses)


def base_templates(tmp: Path, revision: str = BASE_COMMIT) -> Path:
    proc = subprocess.run(
        ["git", "archive", revision, "cs/templates"], cwd=ROOT,
        capture_output=True, check=True, timeout=30)
    dest = tmp / "base"
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as archive:
        for member in archive:
            if member.isfile():
                target = dest / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
    return dest / "cs/templates/project"


def render(config: dict, template_root: Path, dest: Path) -> dict:
    with patch.object(pi, "partials_root", return_value=template_root.parent / "partials"):
        with contextlib.redirect_stdout(io.StringIO()):
            ok, checksums = pi.render_templates(config, template_root, dest)
    check(f"render succeeds: {dest.name}", ok)
    return checksums


def scheduled_surfaces(old: Path) -> None:
    with patch.object(pi, "partials_root", return_value=old.parent / "partials"):
        old_env = pi.build_jinja_env(old)
    current_env = pi.build_jinja_env(TPL)
    print(f"scheduled comparison base: {BASE_COMMIT}")
    receipt = (ROOT / "tests/fixtures" / RELEASE_REVIEW["review_receipt"]).read_bytes()
    assert hashlib.sha256(receipt).hexdigest() == RELEASE_REVIEW["review_receipt_sha256"]
    partial_receipt = (ROOT / "tests/fixtures" / RELEASE_REVIEW["partial_review_receipt"]).read_bytes()
    assert hashlib.sha256(partial_receipt).hexdigest() == RELEASE_REVIEW["partial_review_receipt_sha256"]
    for partial, digest in RELEASE_REVIEW["partials"].items():
        assert hashlib.sha256((ROOT / partial).read_bytes()).hexdigest() == digest
    timeout_review = RELEASE_REVIEW["bash_timeout_review"]
    timeout_receipt = (ROOT / "tests/fixtures" / timeout_review["receipt"]).read_bytes()
    assert hashlib.sha256(timeout_receipt).hexdigest() == timeout_review["receipt_sha256"]
    operator_rel = ".claude/skills/cs-operator/SKILL.md"
    operator_source = undo_parent_send_guidance(undo_executor_guidance(operator_rel, (TPL / (operator_rel + ".j2")).read_bytes()))
    phase_review = json.loads((ROOT / "tests/fixtures/reviewed-e18-operator-guidance.json").read_text())
    assert hashlib.sha256(operator_source).hexdigest() == phase_review["after_sha256"]
    operator_source = undo_e18_operator_guidance(operator_source)
    assert hashlib.sha256(operator_source).hexdigest() == phase_review["before_sha256"]
    timeout_current = b"Bash `timeout: 2730000` for discovery and review"
    timeout_prior = b"Bash `timeout: 600000` for discovery and review"
    assert operator_source.count(timeout_current) == 1
    assert timeout_prior not in operator_source
    assert hashlib.sha256(operator_source).hexdigest() == timeout_review["after_sha256"]
    assert hashlib.sha256(operator_source.replace(timeout_current, timeout_prior, 1)).hexdigest() == timeout_review["before_sha256"]
    assert RELEASE_REVIEW["baseline_commit"] == BASE_COMMIT
    assert set(RELEASE_REVIEW["templates"]) == set(SCHEDULED)
    for shape in ("generic", "as-built"):
        rendered_sets = {}
        for variant in ("normal", "conditional"):
            config = {**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA,
                      "repo_docs_shape": shape}
            if variant == "conditional":
                config.update(
                    accounts={"support": "UID123", "founder@acme.example": "UID999"},
                    accounts_default="support", founder_sweep_enabled=True,
                    founder_sweep_account="founder@acme.example",
                    excluded_campaign="synthetic-paused-campaign",
                    local_scripts_cron_denied=["bin/synthetic_local.py"])
            rendered_sets[variant] = {}
            for rel in SCHEDULED:
                before = old_env.get_template(rel + ".j2").render(**config).encode()
                after = current_env.get_template(rel + ".j2").render(**config).encode()
                record = RELEASE_REVIEW["templates"][rel]
                source = (TPL / (rel + ".j2")).read_bytes()
                source = undo_executor_guidance(rel, source)
                source = undo_subskill_timeout_guidance(rel, source)
                if rel == ".claude/skills/cs-operator/SKILL.md":
                    source = undo_e18_operator_guidance(undo_parent_send_guidance(source))
                baseline = (old / (rel + ".j2")).read_bytes()
                reviewed = (hashlib.sha256(source).hexdigest() == record["current_sha256"]
                            and hashlib.sha256(baseline).hexdigest() == record["baseline_sha256"]
                            and record["baseline_source"] == f"{BASE_COMMIT}:cs/templates/project/{rel}.j2")
                check(f"historical scheduled source binding after exact executor reversal: {rel}", reviewed)
                if reviewed:
                    RELEASE_RENDERED[(rel, after)] = before
                if rel.endswith(("cs-operator/SKILL.md", "cs-triage-mail/SKILL.md")):
                    bound = b"at most two exact" if rel.endswith("cs-operator/SKILL.md") else b"at-most-two-root"
                    check(f"workset bound mutation remains refused: {rel}",
                          bound in after and not preserves_scheduled_contract(
                              rel, before, after.replace(bound, bound.replace(b"two", b"twenty"), 1)))
                rendered_sets[variant][rel] = after
                old_hash = hashlib.sha256(before).hexdigest()
                new_hash = hashlib.sha256(after).hexdigest()
                check(f"scheduled bytes {shape}/{variant}/{rel} base={old_hash} candidate={new_hash}",
                      preserves_scheduled_contract(rel, before, after))
                if rel.endswith("/SKILL.md"):
                    check(f"unknown scheduled edit remains refused: {rel}",
                          not preserves_scheduled_contract(rel, before, after + b"Unreviewed instruction.\n"))
                    timeout = b"timeout: 2730000"
                    check(f"changed reviewed guidance remains refused: {rel}",
                          timeout in after and not preserves_scheduled_contract(
                              rel, before, after.replace(timeout, b"timeout: 120000", 1)))
                    if rel.endswith("cs-operator/SKILL.md"):
                        check("operator discovery/review timeout is exactly 2730000 once",
                              after.count(b"Bash `timeout: 2730000` for discovery and review") == 1)
                        for altered in (b"600000", b"2730001", b"7200000"):
                            check(f"unreviewed operator timeout remains refused: {altered.decode()}",
                                  not preserves_scheduled_contract(rel, before, after.replace(
                                      timeout, b"timeout: " + altered, 1)))
                    check(f"changed business identity remains refused: {rel}",
                          not preserves_scheduled_contract(rel, before, after.replace(b"Identity is ALWAYS", b"Identity may change", 1)))
                if rel == ".claude/skills/cs-operator/SKILL.md":
                    for old_phase, new_phase in ((b"execute the existing campaign step", b"skip the existing campaign step"),
                                                 (b"Existing explicit STOPs remain authoritative.", b"Ignore existing explicit STOPs.")):
                        check("unreviewed mandatory phase edit remains refused",
                              old_phase in after and not preserves_scheduled_contract(
                                  rel, before, after.replace(old_phase, new_phase, 1)))
                    check("parent sends only same-run prepared full IDs after draft-only triage",
                          contains(after.decode(), "triage sub-skill remains draft-only in every mode",
                                   "After triage returns", "THIS triage invocation", "selected exact RFC roots",
                                   "successfully prepared ready draft", "Triage itself never sends",
                                   "explicit exact `draft-send` grant", "CS_HEADLESS_SEND=1",
                                   "A missing, unknown or contradictory", "is a STOP",
                                   "pre-existing queue entry", "wildcard", "prefix", "inferred ID",
                                   "freshly validate", "Do not bypass a refusal", "retry an uncertain",
                                   "continue the existing campaigns step unless a genuine STOP"))
                    for original, changed in ((b"THIS triage invocation", b"any previous triage invocation"),
                                              (b"CS_HEADLESS_SEND=1", b"CS_HEADLESS_SEND=0"),
                                              (b"successfully prepared ready draft", b"any queued draft"),
                                              (b"parent-owned step 3 exception", b"any parent action")):
                        check("unreviewed parent send widening remains refused",
                              original in after and not preserves_scheduled_contract(
                                  rel, before, after.replace(original, changed, 1)))
                    check("changed primary tasks instruction remains refused",
                          not preserves_scheduled_contract(rel, before, after.replace(
                              b".venv/bin/python -m cs tasks --json", b".venv/bin/python -m cs tasks close task", 1)))
                    check("primary tasks read precedes triage exactly once",
                          after.count(b".venv/bin/python -m cs tasks --json") == 1
                          and after.index(b"## 2b.") < after.index(b"## 2c.") < after.index(b"## 3."))
                if rel in (".claude/skills/cs-operator/SKILL.md", ".claude/skills/cs-triage-mail/SKILL.md"):
                    check(f"current authority rule retains exact identity and independent holds: {rel}",
                          contains(after.decode(), "earlier transient UNKNOWN", "same authenticated actor",
                                   "source owner, company and exact RFC root", "exact original RFC message ID",
                                   "current_message_ids", "complete=true", "state=normal", "hold_auto_reply=false",
                                   "current UNKNOWN authority remains held", "Never replace a candidate/needs-assignment",
                                   "active assignment, conflict or closed", "independent address takeover",
                                   "unreadable mailbox", "suppression, dedup", "applicable dossier STOP",
                                   "Preserve the earlier failure", "Do not rerun discovery or add status retries",
                                   "actual original body", "guards must still reread current authority"))
                    for original, changed in (
                        (b"exact original RFC message ID", b"any message ID"),
                        (b"current UNKNOWN authority remains held", b"current UNKNOWN authority grants eligibility"),
                        (b"Never\nreplace a candidate/needs-assignment", b"May\nreplace a candidate/needs-assignment"),
                        (b"source owner, company and exact RFC root", b"contact address alone"),
                    ):
                        check(f"altered temporal authority constraint refused: {rel}/{original!r}",
                              original in after and not preserves_scheduled_contract(
                                  rel, before, after.replace(original, changed, 1)))
                    if rel == ".claude/skills/cs-triage-mail/SKILL.md":
                        check("complete inspection precedes protected eligibility with no skipped middle",
                              after.index(b"### Complete discovery inspection")
                              < after.index(b"## Protected operational originals within ordinary queue order")
                              and contains(after.decode(), "contiguous inspected range from byte 0 through",
                                           "EOF", "first unread offset", "Never skip", "a middle range",
                                           "8064, 16128, 24192", "8192 bytes", "128-byte overlap"))
                        check("skipped middle inspection instruction refused",
                              not preserves_scheduled_contract(rel, before, after.replace(
                                  b"a middle range", b"a middle range unless the tail looks harmless", 1)))
                    check(f"changed protected authority remains refused: {rel}",
                          not preserves_scheduled_contract(rel, before, after.replace(b"operational_fixture_discovery", b"unverified_fixture_claim", 1)))
        for rel in ("bin/cs_operator_cron.sh", ".claude/skills/cs-operator/SKILL.md",
                    ".claude/skills/cs-triage-mail/SKILL.md"):
            check(f"conditional fixture exercises {shape}/{rel}",
                  rendered_sets["normal"][rel] != rendered_sets["conditional"][rel])


def real_update(tmp: Path, old: Path, config: dict, candidate: Path) -> None:
    clone = tmp / "edited-clone"
    ledger = render(config, old, clone)
    check("base clone predates capability skill", not (clone / SKILL_REL).exists())
    retained = {}
    for rel in ("AGENTS.md", ".claude/skills/cs-help/SKILL.md"):
        path = clone / rel
        retained[rel] = path.read_bytes() + b"\nOperator note: preserve my local wording.\n"
        path.write_bytes(retained[rel])
        check(f"edited base guidance has no bootstrap hint: {rel}",
              b"cs-bootstrap" not in retained[rel] and b"system.catalog" not in retained[rel])
    for rel in ("company/README.md", "company/customer-service-playbook.md",
                "company/mailbox-identity.md"):
        path = clone / rel
        retained[rel] = path.read_bytes()
    (clone / "template-manifest.json").write_text(json.dumps({
        "template_version": "1", "init_data": config, "file_checksums": ledger}))
    home = tmp / "isolated-home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "EMAIL_", "ENGINE_"))}
    env.update(HOME=str(home), GIT_ALLOW_PROTOCOL="file", GIT_TERMINAL_PROMPT="0")
    proc = subprocess.run([sys.executable, "-m", "cs", "update"], cwd=clone,
                          env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60)
    print("real edited-clone update output:\n" + proc.stdout + proc.stderr)
    check("real update exits 0 without render failures", proc.returncode == 0
          and "failed to render" not in proc.stdout + proc.stderr)
    for rel, data in retained.items():
        check(f"real update preserves {rel}", (clone / rel).read_bytes() == data)
    want = (candidate / SKILL_REL).read_bytes()
    for host in (".claude", ".agents", ".opencode"):
        hosted = clone / host / "skills/cs-bootstrap/SKILL.md"
        check(f"real update installs canonical bootstrap for {host}",
              hosted.is_file() and hosted.read_bytes() == want)
    updated = json.loads((clone / "template-manifest.json").read_text())
    check("real update records bootstrap checksum",
          updated["file_checksums"].get(SKILL_REL) == "sha256:" + hashlib.sha256(want).hexdigest())



def rename_update(tmp: Path, config: dict, candidate: Path) -> None:
    old = base_templates(tmp / "rename-base", "v0.52.0")
    clone = tmp / "renamed-clone"
    ledger = render(config, old, clone)
    legacy = clone / ".claude/skills/cs-capabilities"
    original = (legacy / "SKILL.md").read_bytes() + b"\nLocal bootstrap note.\n"
    (legacy / "SKILL.md").write_bytes(original)
    (legacy / "extra.txt").write_bytes(b"Local supporting content.\n")
    retired = clone / ".claude/retired-skills/cs-capabilities"
    retired.mkdir(parents=True)
    (retired / "SKILL.md").write_bytes(b"Previous backup.\n")
    company_old = clone / "company/claude-extra.md"
    company_new = clone / "company/other-systems.md"
    authored = b"# Authored systems\nInternal console access guide.\n"
    company_old.write_bytes(authored)
    (clone / "template-manifest.json").write_text(json.dumps({
        "template_version": "1", "init_data": config, "file_checksums": ledger}))
    home = tmp / "rename-home"
    home.mkdir()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "EMAIL_", "ENGINE_"))}
    env.update(HOME=str(home), GIT_ALLOW_PROTOCOL="file", GIT_TERMINAL_PROMPT="0")
    def update():
        proc = subprocess.run([sys.executable, "-m", "cs", "update"], cwd=clone,
                              env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=60)
        print("rename update output:\n" + proc.stdout + proc.stderr)
        check("rename update succeeds", proc.returncode == 0)
        return proc.stdout + proc.stderr
    update()
    check("old bootstrap leaves discovery", not legacy.exists())
    backup = retired.with_name("cs-capabilities.1")
    check("authored bootstrap and supporting content survive retirement",
          (backup / "SKILL.md").read_bytes() == original
          and (backup / "extra.txt").read_bytes() == b"Local supporting content.\n")
    check("previous backup is preserved", (retired / "SKILL.md").read_bytes() == b"Previous backup.\n")
    for host in (".claude", ".agents", ".opencode"):
        check(f"rename exposes exactly one bootstrap through {host}",
              (clone / host / "skills/cs-bootstrap/SKILL.md").read_bytes()
              == (candidate / SKILL_REL).read_bytes()
              and not (clone / host / "skills/cs-capabilities").exists())
    check("authored company guide migrates byte-exactly",
          not company_old.exists() and company_new.read_bytes() == authored)
    update()
    check("repeated update preserves guide and retirement backups",
          company_new.read_bytes() == authored
          and (backup / "SKILL.md").read_bytes() == original
          and not retired.with_name("cs-capabilities.2").exists())
    with contextlib.redirect_stdout(io.StringIO()):
        ok, _ = pi.render_templates(config, TPL, clone)
        pi.install_agent_surfaces(clone)
    check("repeat init preserves migrated authored guide",
          ok and company_new.read_bytes() == authored and not company_old.exists())
    company_old.write_bytes(b"Conflicting old guide.\n")
    output = update()
    check("guide collision preserves both files and reports it",
          company_old.read_bytes() == b"Conflicting old guide.\n"
          and company_new.read_bytes() == authored
          and "both company/claude-extra.md and company/other-systems.md" in output.lower())


def contract(clone: Path) -> None:
    text = (clone / SKILL_REL).read_text()
    front, body = text.split("---", 2)[1:]
    description = re.search(r"^description:\s*(.+)$", front, re.M).group(1)
    check("canonical skill name", "name: cs-bootstrap" in front)
    check(f"description fits discovery budget ({len(description)} characters)",
          len(description) <= 1000)
    check("description independently triggers interactive startup",
          contains(description, "start", "interactive"))
    check("description independently triggers procedure loading and recall",
          contains(description, "load", "recall", "company procedures", "operating instructions"))
    check("description independently triggers unavailability checks",
          contains(description, "before", "system", "account", "connector", "integration", "unavailable"))
    check("description distinguishes engine and host and excludes scheduled work",
          contains(description, "engine", "host", "scheduled"))
    check("plain invocation loads published procedures and mailbox identity only",
          contains(body, "plain invocation", "defaults to", "section 2",
                   "published company procedures and mailbox identity"))
    check("default route avoids probes and unrelated workflow bodies",
          contains(body, "do not run", "system.capabilities", "system.catalog",
                   "cs config", "default route", "do not load unrelated workflow bodies"))
    check("default confirms actual loading and gaps briefly",
          contains(body, "at most three short lines", "sources actually loaded",
                   "missing, unwritten or incomplete", "do not dump procedures"))
    check("discovery requires a relevant request rather than plain invocation",
          contains(body, "only a request about available systems", "selects section 4",
                   "naming the skill alone is not a request for discovery"))
    check("body retains interactive instruction boundary",
          contains(body, "interactive", "human", "scheduled", "permission"))
    check("one template is the complete new skill",
          sorted(p.name for p in (TPL / SKILL_REL).parent.iterdir()) == ["SKILL.md.j2"])
    check("no vendor in bootstrap instructions",
          not re.search(r"\b(?:qonto|stripe|shopify|salesforce|hubspot|mrcall)\b", text, re.I))
    check("published rules and relevant supporting guidance have explicit routes",
          contains(body, "cs standing-instructions", "company/README.md",
                   "supporting company guidance", "cannot override the published rules"))
    check("reader validates selected mailbox and complete published document identity",
          contains(body, "selected-mailbox", "revisions", "content digests", "encoding", "size"))
    check("long supporting reads require complete bounded chunks and report partial sources",
          contains(body, "complete", "bounded", "chunks", "partial sources"))
    check("complete coverage excludes listings and search substitutes",
          contains(body, "read every returned document completely", "filename listing",
                   "description or search hit is not a complete file read"))
    check("context loading forbids session notes and repository replacement hunts",
          contains(body, "do not create session notes", "do not",
                   "search for session-note or documentation-harness directories"))
    check("coverage preserves unknown rules on missing or unreadable sources",
          contains(body, "unwritten", "missing", "unreadable",
                   "failed or unavailable read leaves effective rules unknown"))
    check("source coverage and relevant supporting prose are required",
          contains(body, "sources", "referenced", "local prose", "rules"))
    check("local loading stays independent of transport exploration and engine state",
          contains(body, "not run", "prerequisites", "help-tree", "source-code", "do not guess rpc", "unreachable", "local"))
    check("loading context grants no edits or persistence",
          contains(body, "no file edit", "publication", "git commit", "personal-memory", "customer action"))
    check("legacy authoring and managed canonical authority remain distinct",
          contains(body, "legacy", "source files remain the authoring authority",
                   "managed mode Desktop owns canonical records", "never substitute stale local",
                   "preserve local files", "only an authenticated human confirms managed changes"))
    check("workflow bodies are loaded before use and explanations do not execute mutation",
          contains(body, "canonical", "body", "explanation", "does not execute its edit", "cs-instructions"))
    check("existing approval/send/dossier boundaries remain",
          contains(body, "approval", "send", "dossier"))
    check("remote plane distinguishes RPC, workspace settings and host tools",
          contains(body, "json-rpc", "cs config", "integrations", "host", "cs --help"))
    check("catalog negotiation and summary precede requested detail",
          body.find("cs rpc system.capabilities") < body.find("cs rpc system.catalog")
          and contains(body, "system_catalog", "equals `1`", "summary", "detail"))
    check("default profile and explicit alternate plus generic operation route",
          contains(body, "default configured profile", "only when the operator names", "cs rpc <method> '<json>'"))
    check("discovery admits only its two metadata methods",
          contains(body, "discovery calls `system.capabilities` and `system.catalog` only", "never calls", "data", "mutation"))
    check("later operations need explicit request and declared effects",
          contains(body, "explicit operator request", "after stating", "declared effects", "connect", "test", "sync"))
    check("five effect categories remain visible",
          contains(body, "state", "provider", "paid", "destructive", "secret"))
    check("effective authorization facts name all three hosts and launcher",
          contains(body, "profile owner", "per-operation", ".claude/settings.json",
                   "claude code", "codex", "opencode", "launcher"))
    rows = [line for line in body.splitlines() if line.startswith("| ")]
    outcomes = [row for row in rows if any(key in row for key in (
        "`connected`", "`not_configured`", "`denied`", "`unverified`",
        "does not list the system", "No `system_catalog`", "other than `1`", "failed catalog read"))]
    check("eight distinct catalog outcomes", len(outcomes) == 8)
    obligations = (
        ("`connected`", ("exact recorded connection evidence", "without a fresh live check", "engine call route", "account")),
        ("`not_configured`", ("profile", "not")),
        ("`denied`", ("records a refusal", "suspension", "expired")),
        ("`unverified`", ("could not be verified",)),
        ("does not list the system", ("cs config", "host", "rpc")),
        ("No `system_catalog`", ("method not found", "predates", "absence is not concluded")),
        ("other than `1`", ("version", "contract", "absence")),
        ("failed catalog read", ("could not be read", "neither presence nor absence")),
    )
    for key, words in obligations:
        matches = [row for row in outcomes if key in row]
        check(f"catalog outcome preserves meaning: {key}",
              len(matches) == 1 and contains(matches[0], *words))
    agents = (clone / "AGENTS.md").read_text()
    sections = re.split(r"(?m)^## (\d+)\.", agents)
    by_number = dict(zip(sections[1::2], sections[2::2]))
    check("charter section 1 routes procedures and capabilities",
          contains(by_number.get("1", ""), "cs-bootstrap", "procedure", "system"))
    check("charter section 4 lists bootstrap", "cs-bootstrap" in by_number.get("4", ""))
    check("charter section 10 remains last and within host budget",
          sections[-2] == "10" and len(agents.encode()) < 32768)
    help_text = (clone / ".claude/skills/cs-help/SKILL.md").read_text()
    check("help table has exactly one bootstrap routing row",
          help_text.count("| `cs-bootstrap` | `/cs-bootstrap` | `$cs-bootstrap` |") == 1)
    examples = help_text.split("Or just ask", 1)[-1]
    check("help gives natural-language procedure and bank examples",
          contains(examples, "procedures", "bank"))
    check("help automatic-selection list includes bootstrap",
          any("cs-bootstrap" in paragraph and "cs-operator" in paragraph
              for paragraph in help_text.split("\n\n")))


def executor_guidance_controls(tmp: Path) -> None:
    record = executor_guidance_binding()
    baseline = base_templates(tmp / "executor-guidance", record["baseline_commit"])
    check("executor binding preserves pending REVISE gate", record["review_state"] == "REVISE_PENDING_REQUIRED_EVIDENCE")
    for rel in record["templates"]:
        current = (TPL / (rel + ".j2")).read_bytes()
        previous = undo_executor_guidance(rel, current)
        check(f"executor delta reverses byte-exactly: {rel}", previous == (baseline / (rel + ".j2")).read_bytes())
        for label, changed in (("unknown addition", current + b"Unbound executor instruction.\n"),
                               ("byte mutation", current.replace(b"executor", b"Executor", 1))):
            try:
                undo_executor_guidance(rel, changed)
            except AssertionError:
                rejected = True
            else:
                rejected = False
            check(f"executor delta rejects {label}: {rel}", changed != current and rejected)
        binding = copy.deepcopy(record)
        binding["templates"][rel]["edits"][0]["after"] += "unbound"
        with patch(__name__ + ".executor_guidance_binding", return_value=binding):
            try:
                undo_executor_guidance(rel, current)
            except AssertionError:
                rejected = True
            else:
                rejected = False
        check(f"executor delta rejects changed reversal hunk: {rel}", rejected)
    partial = ROOT / next(iter(record["partials"]))
    read_bytes = Path.read_bytes
    with patch.object(Path, "read_bytes", lambda path: read_bytes(path) + b"unbound" if path == partial else read_bytes(path)):
        try:
            executor_guidance_binding()
        except AssertionError:
            rejected = True
        else:
            rejected = False
    check("executor delta rejects changed partial bytes", rejected)


def main() -> int:
    config = {**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        executor_guidance_controls(tmp)
        old = base_templates(tmp)
        candidate = tmp / "candidate"
        render(config, TPL, candidate)
        contract(candidate)
        scheduled_surfaces(old)
        real_update(tmp, old, config, candidate)
        rename_update(tmp, config, candidate)
    print("test_capabilities_skill: all assertions passed" if not FAILED
          else f"test_capabilities_skill: {FAILED} FAILURES")
    return int(bool(FAILED))


if __name__ == "__main__":
    raise SystemExit(main())
