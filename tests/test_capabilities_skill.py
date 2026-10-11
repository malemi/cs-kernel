#!/usr/bin/env python3
"""Deterministic bootstrap contract, upgrade and scheduled-surface checks.

These checks establish what the rendered instructions say and what real stamping
preserves. Native host acceptance separately proves agent selection and behavior.
The comparison base is the reviewed legal-skill tip preceding this bootstrap.
"""
from __future__ import annotations

import contextlib
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
                rendered_sets[variant][rel] = after
                old_hash = hashlib.sha256(before).hexdigest()
                new_hash = hashlib.sha256(after).hexdigest()
                check(f"scheduled bytes {shape}/{variant}/{rel} base={old_hash} candidate={new_hash}",
                      before == after)
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
    check("plain invocation loads local procedures and mailbox identity only",
          contains(body, "plain invocation", "defaults to", "section 2",
                   "local company procedures and mailbox identity"))
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
    check("known company source routes are explicit",
          contains(body, "company/README.md", "company/customer-service-playbook.md",
                   "company/mailbox-identity.md", "company/mailboxes/<email>.md"))
    check("mailbox exception requires explicit selection and absence of its own clone",
          contains(body, "explicitly selected", "own clone"))
    check("long instruction reads require complete bounded chunks and handle truncation",
          contains(body, "complete", "bounded", "chunks", "truncated", "remaining"))
    check("complete coverage excludes filtered/count-only substitutes and skipped ranges",
          contains(body, "first unread position", "never skip a middle range",
                   "filtered results", "do not load omitted contents", "report partial loading"))
    check("context loading forbids session notes and repository replacement hunts",
          contains(body, "do not create session notes", "named paths",
                   "instead of searching the repository for replacements"))
    check("coverage separates authored, unwritten, missing and unreadable inputs",
          contains(body, "authored", "## What to write here", "unwritten", "missing", "unreadable"))
    check("source coverage and relevant supporting prose are required",
          contains(body, "sources", "referenced", "local prose", "rules"))
    check("local loading stays independent of transport exploration and engine state",
          contains(body, "not run", "prerequisites", "help-tree", "source-code", "do not guess rpc", "unreachable", "local"))
    check("loading context grants no edits or persistence",
          contains(body, "no file edit", "publication", "git commit", "personal-memory", "customer action"))
    check("local files retain authority over the derived engine mirror",
          contains(body, "company files are authoritative", "compiled copy", "do not silently substitute", "mirror"))
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


def main() -> int:
    config = {**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
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
