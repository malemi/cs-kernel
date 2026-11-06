"""Gate: every agent resolves the same project-scoped skills.

The canonical render lives under `.claude/skills`. Codex and OpenCode receive
repository links to that tree; command-era project mirrors and home-global
Codex prompts are retired by an exact, closed name set. Unrelated user files
must survive, and filesystems without symlink support receive equivalent
copies. `AGENTS.md` is a rendered file — the charter — and the wiring never
links, replaces or removes it.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cs import project_init as pi  # noqa: E402
from test_legal_research_skill import LEGAL_FILES  # noqa: E402

FAILED = 0


def check(label: str, cond: bool) -> None:
    global FAILED
    print(f"  {'ok  ' if cond else 'FAIL'} {label}")
    if not cond:
        FAILED += 1


def _clone(root: Path, name: str) -> Path:
    clone = root / name
    for skill in ("cs-review", "cs-help", "cs-instructions"):
        path = clone / ".claude" / "skills" / skill / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(f"---\nname: {skill}\ndescription: {name}\n---\n")
    (clone / "CLAUDE.md").write_text("@AGENTS.md\n")
    (clone / "AGENTS.md").write_text(f"# charter of {name}\n")
    return clone


@contextlib.contextmanager
def _legacy_prompts(tmp: Path, name: str = "codex-prompts"):
    real = pi.LEGACY_CODEX_PROMPTS
    pi.LEGACY_CODEX_PROMPTS = tmp / name
    try:
        yield pi.LEGACY_CODEX_PROMPTS
    finally:
        pi.LEGACY_CODEX_PROMPTS = real


def _seed_legacy(clone: Path, prompts: Path) -> None:
    for directory in (clone / ".opencode" / "commands", prompts):
        directory.mkdir(parents=True)
        for name in pi.RETIRED_COMMAND_NAMES:
            (directory / name).write_text("obsolete\n")
        (directory / "mine.md").write_text("keep\n")



def bootstrap_profile_controls(tmp: Path) -> None:
    import cs
    from cs import project_update as pu
    from test_project_update import _FULL_INIT_DATA

    package = tmp / "profile-package"
    templates = package / "templates/project"
    templates.mkdir(parents=True)
    charter = "# Shared fixture charter"
    (templates / "AGENTS.md.j2").write_text(charter)
    (templates / "CLAUDE.md").write_bytes((ROOT / "cs/templates/project/CLAUDE.md").read_bytes())
    skill = templates / ".claude/skills/example/SKILL.md.j2"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Shared fixture skill\n")
    valid = "harness_version = 9\nindex_file = AGENTS.md\ninventory_ignore =\n"

    def seed(name, profile=valid):
        root = tmp / name
        (root / "docs").mkdir(parents=True)
        (root / ".git").mkdir()
        (root / "AGENTS.md").write_text(charter)
        if profile is not None:
            (root / "docs/.doc-profile").write_text(profile)
        rule = root / ".claude/rules/project-instructions.md"
        rule.parent.mkdir(parents=True)
        rule.symlink_to("../../AGENTS.md")
        return root

    def initialize(root):
        with patch.object(cs, "__file__", str(package / "__init__.py")), \
                patch.object(pi, "collect_config", return_value={**_FULL_INIT_DATA, "dest_dir": str(root)}), \
                patch.object(pi, "prompt_yes_no", return_value=True), \
                patch.object(pi, "write_state_env"), \
                patch.object(pi, "offer_project_install", return_value=None), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return pi.cmd_init([])

    def update(root):
        previous = Path.cwd()
        output = io.StringIO()
        try:
            os.chdir(root)
            with patch.object(cs, "__file__", str(package / "__init__.py")), \
                    patch("builtins.input", side_effect=EOFError), \
                    contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                result = pu.cmd_update([])
        finally:
            os.chdir(previous)
        return result, output.getvalue()

    with _legacy_prompts(tmp, "profile-prompts"):
        root = seed("managed-profile")
        check("actual init succeeds with v9 AGENTS-only layout", initialize(root) == 0)
        check("actual init does not create v9 CLAUDE bootstrap", not (root / "CLAUDE.md").exists())
        check("v9 init preserves profile and charter", (root / "docs/.doc-profile").read_text() == valid
              and (root / "AGENTS.md").read_text() == charter)
        preserved = root / "AGENTS.md"
        preserved.write_text(charter + "\nLocal managed instructions\n")
        (templates / "AGENTS.md.j2").write_text(charter + "\nChanged upstream instructions\n")
        for iteration in range(2):
            result, output = update(root)
            check(f"actual v9 update {iteration + 1} succeeds and explains omission",
                  result == 0 and "harness v9 uses AGENTS.md directly" in output)
            check(f"actual v9 update {iteration + 1} cannot resurrect CLAUDE",
                  not (root / "CLAUDE.md").exists())
            check(f"actual v9 update {iteration + 1} retains declined AGENTS conflict",
                  preserved.read_text() == charter + "\nLocal managed instructions\n")
        for host in (".agents", ".opencode"):
            check(f"v9 {host} alias retains canonical skill bytes",
                  (root / host / "skills").is_symlink()
                  and os.readlink(root / host / "skills") == "../.claude/skills"
                  and (root / host / "skills/example/SKILL.md").read_bytes()
                  == (root / ".claude/skills/example/SKILL.md").read_bytes())
        check("v9 Claude rules link remains exact", os.readlink(root / ".claude/rules/project-instructions.md")
              == "../../AGENTS.md")
        custom = root / "CLAUDE.md"
        custom.write_text("# Existing custom bootstrap\n")
        custom.chmod(0o640)
        before = custom.read_bytes()
        result, _ = update(root)
        check("v9 update preserves existing custom CLAUDE bytes and mode",
              result == 0 and custom.read_bytes() == before and custom.stat().st_mode & 0o777 == 0o640)
        ledger = json.loads((root / "template-manifest.json").read_text())
        ledger["file_checksums"]["CLAUDE.md"] = pu._checksum(custom.read_text())
        (root / "template-manifest.json").write_text(json.dumps(ledger))
        result, _ = update(root)
        check("v9 cannot refresh even a ledgered existing CLAUDE",
              result == 0 and custom.read_bytes() == before)
        custom.unlink()
        external = tmp / "custom-instructions.md"
        external.write_text("Preserve external custom instructions")
        custom.symlink_to(external)
        result, _ = update(root)
        check("v9 update preserves an existing custom CLAUDE link and its target",
              result == 0 and custom.is_symlink()
              and external.read_text() == "Preserve external custom instructions")
        custom.unlink()
        with patch.object(pi, "bootstrap_profile_mode", return_value="legacy"):
            result, _ = update(root)
        check("removing v9 guard reproduces actual update resurrection",
              result == 0 and custom.read_bytes() == (templates / "CLAUDE.md").read_bytes())

        legacy = seed("legacy-profile", None)
        check("actual legacy init still creates original bootstrap",
              initialize(legacy) == 0 and (legacy / "CLAUDE.md").read_bytes()
              == (templates / "CLAUDE.md").read_bytes())
        (legacy / "CLAUDE.md").unlink()
        result, _ = update(legacy)
        check("actual legacy update still restores absent bootstrap",
              result == 0 and (legacy / "CLAUDE.md").read_bytes()
              == (templates / "CLAUDE.md").read_bytes())
        (legacy / "AGENTS.md").unlink()
        check("missing legacy charter still refuses bootstrap", not pi.bootstrap_may_land(legacy, "CLAUDE.md"))
        (legacy / "AGENTS.md").symlink_to("CLAUDE.md")
        check("symlink legacy charter still refuses bootstrap", not pi.bootstrap_may_land(legacy, "CLAUDE.md"))

        cases = ["", "not a profile\n", "harness_version = 8\nindex_file = CLAUDE.md\n",
                 "harness_version = 10\nindex_file = AGENTS.md\n",
                 valid + "harness_version = 9\n", valid + "harness_file =\n",
                 "harness_version = 9\nindex_file = CLAUDE.md\n",
                 'harness_version = 9\nindex_file = "AGENTS.md\n']
        for number, profile in enumerate(cases):
            bad = seed(f"invalid-profile-{number}", profile)
            (bad / "template-manifest.json").write_text(json.dumps({"init_data": {}, "file_checksums": {}}))
            before_agents = (bad / "AGENTS.md").read_bytes()
            before_manifest = (bad / "template-manifest.json").read_bytes()
            result, output = update(bad)
            check(f"invalid profile {number} refuses update before writes with diagnosis",
                  result == 1 and "unresolved instruction layout" in output
                  and not (bad / "CLAUDE.md").exists()
                  and (bad / "AGENTS.md").read_bytes() == before_agents
                  and (bad / "template-manifest.json").read_bytes() == before_manifest)
            check(f"invalid profile {number} refuses init before writes", initialize(bad) == 1
                  and not (bad / "CLAUDE.md").exists()
                  and (bad / "AGENTS.md").read_bytes() == before_agents)
        unsafe = seed("linked-profile")
        profile = unsafe / "docs/.doc-profile"
        profile.rename(unsafe / "profile.txt")
        profile.symlink_to("../profile.txt")
        check("symlink profile refuses actual init", initialize(unsafe) == 1
              and not (unsafe / "CLAUDE.md").exists())
        (templates / "AGENTS.md.j2").write_text("{{ missing_charter_value }}")
        failed = seed("failed-legacy-render", None)
        (failed / "AGENTS.md").unlink()
        check("failed legacy charter render cannot publish dangling bootstrap",
              initialize(failed) == 1 and not (failed / "CLAUDE.md").exists())


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        bootstrap_profile_controls(tmp)
        clone = _clone(tmp, "acme-cs")

        print("project-scoped skill wiring and exact legacy cleanup")
        with _legacy_prompts(tmp) as prompts:
            _seed_legacy(clone, prompts)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                pi.install_agent_surfaces(clone)

            canonical = clone / ".claude" / "skills"
            codex = clone / ".agents" / "skills"
            opencode = clone / ".opencode" / "skills"
            check("Codex skills are a repository symlink", codex.is_symlink())
            check("OpenCode skills are a repository symlink", opencode.is_symlink())
            check("Codex resolves canonical bytes",
                  (codex / "cs-review/SKILL.md").read_bytes()
                  == (canonical / "cs-review/SKILL.md").read_bytes())
            check("OpenCode resolves canonical bytes",
                  (opencode / "cs-help/SKILL.md").read_bytes()
                  == (canonical / "cs-help/SKILL.md").read_bytes())
            agents = clone / "AGENTS.md"
            check("AGENTS.md is the rendered charter, never a link",
                  agents.is_file() and not agents.is_symlink()
                  and agents.read_text() == "# charter of acme-cs\n")
            check("all retired OpenCode commands are gone",
                  all(not (clone / ".opencode/commands" / n).exists()
                      for n in pi.RETIRED_COMMAND_NAMES))
            check("all retired global prompts are gone",
                  all(not (prompts / n).exists() for n in pi.RETIRED_COMMAND_NAMES))
            check("unrelated OpenCode command survives",
                  (clone / ".opencode/commands/mine.md").read_text() == "keep\n")
            check("unrelated global prompt survives",
                  (prompts / "mine.md").read_text() == "keep\n")
            check("cleanup is reported", "Retired 10 obsolete" in out.getvalue())

            with contextlib.redirect_stdout(io.StringIO()):
                pi.install_agent_surfaces(clone)
            check("a second wiring pass is idempotent",
                  (codex / "cs-review/SKILL.md").is_file())

        print("rendered customer workflow is shared and projects stay outside docs")
        from test_project_update import _FULL_INIT_DATA
        rendered = tmp / "rendered-cs"
        rendered.mkdir()
        with _legacy_prompts(tmp, "rendered-prompts"):
            with contextlib.redirect_stdout(io.StringIO()):
                pi.render_templates({**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA},
                                    ROOT / "cs/templates/project", rendered)
                pi.install_agent_surfaces(rendered)
        customer = rendered / ".claude/skills/cs-customer/SKILL.md"
        triage = rendered / ".claude/skills/cs-triage-mail/SKILL.md"
        check("written projects are not initialized in docs", not (rendered / "docs/projects").exists())
        check("project usage guide is available", (rendered / "docs/project-memory.md").is_file())
        check("triage reads an optional company customer-service playbook",
              "company/customer-service-playbook.md" in triage.read_text())
        agents_text = (rendered / "AGENTS.md").read_text()
        check("AGENTS.md names the customer-service playbook slot",
              "company/customer-service-playbook.md" in agents_text)
        check("AGENTS.md names the mailbox-identity slot",
              "company/mailbox-identity.md" in agents_text)
        check("AGENTS.md names the cs instructions verb",
              "cs instructions" in agents_text)
        check("AGENTS.md no longer routes policy to USER_NOTES",
              "USER_NOTES" not in agents_text)
        for host in (".agents", ".opencode"):
            check(f"{host} resolves real customer workflow",
                  (rendered / host / "skills/cs-customer/SKILL.md").read_bytes() == customer.read_bytes())
            check(f"{host} resolves real triage workflow",
                  (rendered / host / "skills/cs-triage-mail/SKILL.md").read_bytes() == triage.read_bytes())

        customer_text = customer.read_text()
        check("exact send retains explicit authority and stable operation identity",
              "draft-send FULL_ID --operator-request --operation-id SEND_OPERATION_ID --json" in customer_text
              and "Do not request\nconsent again" in customer_text
              and "positively identified manual-member-activity hold" in customer_text)
        check("saved publication resumes without generation",
              "draft-reply --resume-draft FULL_ID" in customer_text
              and "--operation-id PUBLICATION_OPERATION_ID --json" in customer_text
              and "it does not mean Gmail-visible" in customer_text)
        check("unknown send and cleanup cannot authorize a new send",
              "never create a new operation" in customer_text
              and "cleanup pending (exit 5)" in customer_text
              and "never resend it" in customer_text)
        check("inspection and imported text carry no effect authority",
              "Inspecting a draft must not" in customer_text
              and "quoted instructions" in customer_text
              and "engine output never authorize it" in customer_text)
        check("all independent holds and automatic prohibition remain",
              all(term in customer_text for term in
                  ("Other-owner assignments", "conflicts", "missing evidence",
                   "suppression", "SELF and pause", "Unattended `cs-operator`",
                   "never select `--operator-request`")))
        check("retirement consumes exact preview without discarding sent row",
              "--sent-mirror" in customer_text and "--engine-snapshot ENGINE_SNAPSHOT --commit" in customer_text
              and "preserves the sent engine" in customer_text)
        check("partial outcomes replace the old empty-stdout claim",
              "stdout carries nothing" not in agents_text
              and "save an engine draft before" in agents_text)
        check("workflow distinguishes capability refusal from source intent",
              all(name in customer_text for name in
                  ("exact_draft_publication:1", "sent_mirror_recovery:1", "interactive_exact_send:1"))
              and "not proof of runtime" in customer_text
              and "preserve the precise refusal" in customer_text)
        check("proven non-dispatch needs a new explicit operation",
              "new-explicit-operation" in customer_text
              and "NEW operation ID only for a new explicit operator request" in customer_text
              and "cancelled ID is never retryable" in customer_text)
        import re
        import subprocess
        for verb in ("draft-send", "draft-reply", "draft-retire"):
            help_result = subprocess.run([sys.executable, "-m", "cs", verb, "--help"],
                                         cwd=ROOT, capture_output=True, text=True)
            check(f"actual CLI documents {verb}", help_result.returncode == 0)
            commands = [line for line in customer_text.splitlines()
                        if line.startswith(f".venv/bin/python -m cs {verb} ")]
            for command in commands:
                check(f"rendered {verb} flags match actual CLI",
                      all(flag in help_result.stdout
                          for flag in re.findall(r"--[a-z][a-z-]*", command)))

        capabilities = rendered / ".claude/skills/cs-bootstrap/SKILL.md"
        check("capability bootstrap is rendered", capabilities.is_file())
        for host in (".claude", ".agents", ".opencode"):
            hosted = rendered / host / "skills/cs-bootstrap/SKILL.md"
            check(f"{host} resolves canonical bootstrap bytes",
                  capabilities.is_file() and hosted.is_file()
                  and hosted.read_bytes() == capabilities.read_bytes())

        instructions = rendered / ".claude/skills/cs-instructions/SKILL.md"
        check("standing-rule skill is rendered", instructions.is_file())
        text = instructions.read_text()
        check("standing-rule commit exception is explicit beside safety rule",
              "sole standing-rule exception" in agents_text
              and "explicit paths only" in agents_text)
        check("AGENTS routes conversational teaching to the canonical skill",
              "Invoke `cs-instructions`" in agents_text)
        check("triage routes without duplicating the publishing procedure",
              "invoke that skill" in triage.read_text()
              and "run `cs instructions --commit`" not in triage.read_text())
        for host in (".agents", ".opencode"):
            check(f"{host} resolves real standing-rule workflow",
                  (rendered / host / "skills/cs-instructions/SKILL.md").read_bytes()
                  == instructions.read_bytes())
        check("withdrawal verifies both playbook destinations",
              "BOTH `procedures.md` and `phone.md`" in text
              and "Do not delete/empty the file" in text)

        # The one skill that carries supporting files: references, a
        # provenance record and a helper sit beside its SKILL.md, and every
        # host must resolve all of them, not just the entry point.
        legal = rendered / ".claude/skills/cs-legal-research"
        check("legal-research skill is rendered with its supporting files",
              all((legal / rel).is_file() for rel in LEGAL_FILES))
        for host in (".agents", ".opencode"):
            hosted = rendered / host / "skills/cs-legal-research"
            check(f"{host} resolves every legal-research file",
                  all((hosted / rel).is_file() and (legal / rel).is_file()
                      and (hosted / rel).read_bytes() == (legal / rel).read_bytes()
                      for rel in LEGAL_FILES))

        company_rendered = tmp / "company-cs"
        company_rendered.mkdir()
        with _legacy_prompts(tmp, "company-prompts"):
            with contextlib.redirect_stdout(io.StringIO()):
                pi.render_templates({**pi.TEMPLATE_DEFAULTS, **_FULL_INIT_DATA,
                                     "repo_docs_shape": "as-built"},
                                    ROOT / "cs/templates/project", company_rendered)
                pi.install_agent_surfaces(company_rendered)
        for host in (".claude", ".agents", ".opencode"):
            check(f"company clone {host} resolves canonical standing-rule bytes",
                  (company_rendered / host / "skills/cs-instructions/SKILL.md").read_bytes()
                  == instructions.read_bytes())

        print("fresh clones create no command surface")
        fresh = _clone(tmp, "fresh-cs")
        with _legacy_prompts(tmp, "fresh-prompts"):
            with contextlib.redirect_stdout(io.StringIO()):
                pi.install_agent_surfaces(fresh)
        check("no .claude/commands directory", not (fresh / ".claude/commands").exists())
        check("no .opencode/commands directory", not (fresh / ".opencode/commands").exists())

        print("a filesystem that refuses symlinks")
        nolink = _clone(tmp, "win-cs")
        (nolink / ".claude/skills/cs-instructions/SKILL.md").write_bytes(instructions.read_bytes())
        shutil.copytree(legal, nolink / ".claude/skills/cs-legal-research")
        shutil.copytree(customer.parent, nolink / ".claude/skills/cs-customer")
        shutil.copytree(triage.parent, nolink / ".claude/skills/cs-triage-mail")
        shutil.copytree(capabilities.parent, nolink / ".claude/skills/cs-bootstrap")
        retired_content = {}
        for host in (".agents", ".opencode"):
            old = nolink / host / "skills/cs-capabilities"
            old.mkdir(parents=True)
            retired_content[host] = f"Authored legacy content for {host}.\n".encode()
            (old / "SKILL.md").write_bytes(retired_content[host])
            (old / "support.txt").write_bytes(b"Local supporting content.\n")
        real_symlink = Path.symlink_to

        def refuse(self, target, target_is_directory=False):
            raise OSError("symlinks not supported")

        Path.symlink_to = refuse
        try:
            with _legacy_prompts(tmp, "win-prompts"):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    pi.install_agent_surfaces(nolink)
            codex_copy = nolink / ".agents/skills/cs-help/SKILL.md"
            opencode_copy = nolink / ".opencode/skills/cs-review/SKILL.md"
            check("Codex falls back to a real skill copy",
                  codex_copy.is_file() and not (nolink / ".agents/skills").is_symlink())
            check("fallback copy has canonical content",
                  codex_copy.read_bytes()
                  == (nolink / ".claude/skills/cs-help/SKILL.md").read_bytes())
            check("OpenCode fallback also has canonical content",
                  opencode_copy.read_bytes()
                  == (nolink / ".claude/skills/cs-review/SKILL.md").read_bytes())
            for host in (".agents", ".opencode"):
                for name, canonical in (("cs-customer", customer), ("cs-triage-mail", triage)):
                    check(f"{host} copies exact {name} workflow without symlinks",
                          (nolink / host / "skills" / name / "SKILL.md").read_bytes()
                          == canonical.read_bytes())
            for host in (".agents", ".opencode"):
                check(f"{host} copies standing-rule skill without symlinks",
                      (nolink / host / "skills/cs-instructions/SKILL.md").read_bytes()
                      == (nolink / ".claude/skills/cs-instructions/SKILL.md").read_bytes())
            for host in (".agents", ".opencode"):
                hosted = nolink / host / "skills/cs-legal-research"
                check(f"{host} copies every legal-research file without symlinks",
                      not (nolink / host / "skills").is_symlink()
                      and all((hosted / rel).is_file()
                              and (hosted / rel).read_bytes() == (legal / rel).read_bytes()
                              for rel in LEGAL_FILES))
            for host in (".agents", ".opencode"):
                hosted = nolink / host / "skills/cs-bootstrap/SKILL.md"
                check(f"{host} copies bootstrap without symlinks",
                      not (nolink / host / "skills").is_symlink()
                      and hosted.is_file()
                      and hosted.read_bytes() == capabilities.read_bytes())
            for host in (".agents", ".opencode"):
                backup = nolink / ".claude/retired-skills" / f"cs-capabilities.{host[1:]}"
                check(f"{host} authored legacy copy survives outside discovery",
                      (backup / "SKILL.md").read_bytes() == retired_content[host]
                      and (backup / "support.txt").read_bytes() == b"Local supporting content.\n"
                      and not (nolink / host / "skills/cs-capabilities").exists())
            with _legacy_prompts(tmp, "win-repeat-prompts"):
                with contextlib.redirect_stdout(io.StringIO()):
                    pi.install_agent_surfaces(nolink)
            check("copy-fallback retirement is idempotent",
                  all((nolink / ".claude/retired-skills" / f"cs-capabilities.{host[1:]}" / "SKILL.md").read_bytes()
                      == retired_content[host] for host in (".agents", ".opencode")))
            check("copy fallback is disclosed", "copied" in out.getvalue())
            check("AGENTS.md is untouched on a symlink-less filesystem",
                  (nolink / "AGENTS.md").read_text() == "# charter of win-cs\n")
        finally:
            Path.symlink_to = real_symlink

    print("test_agent_surfaces: all assertions passed" if not FAILED
          else f"test_agent_surfaces: {FAILED} FAILURES")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
