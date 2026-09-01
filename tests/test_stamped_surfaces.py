#!/usr/bin/env python3
"""What every clone actually receives: one shared preamble, and no Italian.

Two independent properties of the stamped surfaces, gated together because both
are about the RENDER rather than the source.

**The preamble is one text, included three times.** `.claude/skills/cs-review`
and the `cs-triage-mail` / `cs-operator` skills all open by framing the agent as
an assistant taking over a desk somebody else worked at. Three copies of that
text would be three texts within two releases, so it lives in a partials root
(`cs/templates/partials/`) that is a SIBLING of the project template root — a
partial inside would be stamped into every clone as an orphan `.claude/` file.
That arrangement has exactly one failure mode, and it is invisible at `cs init`:
`cs update` used to build its Jinja environment with NO loader, so the first
`{% include %}` would render fine for a new clone and raise "no loader for this
environment specified" on every existing one. Both stamping paths are therefore
exercised here, not just the easy one.

**No Italian reaches a clone that did not ask for it.** The kernel default is a
US-English product; the voice a clone's surfaces address ITS operator in is
`[surface] operator_voice` in that clone's own `manifest.toml`, free text that
the templates paste into their greeting instruction. A clone that declares
nothing gets the kernel default, and the rendered tree must read as native
English — including `cs review`'s own digest, which is kernel Python and takes
no voice at all.

Asserted here:

  A. The preamble text exists ONCE in the kernel, in the partials root, and the
     three surfaces reach it by `{% include %}`.
  B. `cs init`'s own render (`render_templates`, the real function) puts it in
     all three stamped files — and does NOT stamp the partial itself into the
     clone.
  C. A REAL `cs update` run against a clone whose frozen `init_data` predates
     both the include and the `operator_voice` variable renders all three
     surfaces without a Jinja error.
  D. `manifest.toml` reaches the stamp: the two template-only keys a clone
     declares for itself — `[surface] operator_voice` and `[local_scripts]
     cron_denied` — both arrive through `cs update` without re-running `cs
     init`, against a frozen `init_data` that predates them, and a clone that
     declares no voice gets the kernel default. The second key is the one
     whose failure is a permission hole: the executables it names must come
     out denied in the stamped `bin/cs_operator_cron.sh`, in every spelling.
  E. Nothing Italian survives in the rendered `.claude/` tree stamped from the
     DEFAULT manifest, nor in `cs review`'s digest.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cs import project_init, review  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "cs" / "templates" / "project"
PARTIALS = ROOT / "cs" / "templates" / "partials"

# A sentence of the preamble long enough that no other file says it by accident.
PREAMBLE_MARK = "taking over a desk that was already being worked"
INCLUDE = '{% include "desk-preamble.md.j2" %}'

# The outbound-fact-sourcing partial: memory-first rule for anything that
# leaves the desk in an outbound message. Its marker is an HTML comment
# (the partial carries no heading — it lands inside a numbered section and
# inside skill bullet lists, so a `##` would open a sibling section). A
# second, PROSE mark is asserted alongside it: the comment alone only catches
# a future surface that includes the partial by name — a copy-paste of the
# rule's TEXT into a fourth surface carries no comment and would otherwise
# pass every assertion below.
OUTBOUND_MARK = "<!-- outbound-fact-sourcing -->"
OUTBOUND_PROSE_MARK = (
    "Repository source code is never a source for a customer-facing fact."
)
OUTBOUND_INCLUDE = '{% include "outbound-fact-sourcing.md.j2" %}'
OUTBOUND_SURFACES = (
    "CLAUDE.md",
    ".claude/skills/cs-triage-mail/SKILL.md",
    ".claude/skills/cs-campaign-tick/SKILL.md",
)

# Invented, and it must stay invented: no real clone's filename belongs in
# kernel code, fixtures included. What is under test is the mechanism.
SAMPLE_SCRIPT = "bin/example_tool.py"

SURFACES = (
    ".claude/skills/cs-review/SKILL.md",
    ".claude/skills/cs-triage-mail/SKILL.md",
    ".claude/skills/cs-operator/SKILL.md",
)

# Words that are Italian and nothing else. Kept to terms that cannot appear in
# an English sentence about mail (no "e", no "la"): a wordlist that
# false-positives gets deleted by the next person in a hurry.
ITALIAN = (
    "bozza", "bozze", "ometti", "nulla da fare", "servono te", "fammi sapere",
    "una riga", "presi in carico", "gestiti fuori", "coda support", "campagne",
    "riconciliati", "promemoria", "scartati", "verdetto", "candidati",
    "destinatario", "oggetto", "decisione tua", "in pausa", "esiti",
    "ultimo tick", "italian, founders", "dimmi", "dimmelo", "partiamo",
    "valore in forza", "dichiarato in", "perché", "anomalie",
)

BASE = dict(
    company_name="Acme Corp", company_display_name="Acme",
    company_from_name="Acme Support", company_slug="acme",
    company_prog_name="acme-cs", email_address="support@acme.example",
    engine_owner_uid="UID123", engine_ws_url="wss://engines.example.com",
    platform_env_path="", producer_adapter="none", producer_mrcall_tracking=False,
    crm_adapter="none", crm_shopify=False, drive_scope="",
    cs_triage_mode="draft", dedup_days="30", reminder_max="2",
    system_senders="", send_guard_min_chars=40, send_guard_banned_phrases="",
    sms_enabled=False, sms_hour="18", sms_proxy_base="",
    smtp_host="smtp.example.com", smtp_port="587",
    imap_host="imap.example.com", imap_port="993", timezone="Europe/Rome",
    cron_comment="acme-cs", cron_schedule="0 6-18/2 * * 2-5",
    firebase_sa_path="~/.acme-cs/firebase-sa.json",
    founder_sweep_enabled=False, founder_sweep_account="",
    excluded_campaign="", repo_docs_shape="generic",
    repo_git_remote="", repo_kernel_version="0.1.0",
    name="Acme", accounts={"support": "UID123"}, accounts_default="support",
    operator_voice=project_init.DEFAULT_OPERATOR_VOICE,
    local_scripts_cron_denied=[],
)

fails = 0


def check(cond, msg: str) -> None:
    global fails
    if not cond:
        print(f"  FAIL: {msg}")
        fails += 1


def italian_hits(text: str) -> list[str]:
    """Whole-word matches only: `anomalie` must not fire on `anomalies`, which
    is how a wordlist gate earns the reputation that gets it deleted."""
    low = text.lower()
    return [w for w in ITALIAN
            if re.search(rf"\b{re.escape(w)}\b", low)]


# ---------------------------------------------------------------------- A

def _one_canonical_text() -> None:
    holders = [p for p in (ROOT / "cs").rglob("*")
               if p.is_file() and p.suffix in (".j2", ".py", ".md")
               and PREAMBLE_MARK in p.read_text(errors="replace")]
    check(holders == [PARTIALS / "desk-preamble.md.j2"],
          f"the preamble text must exist EXACTLY once in the kernel, in the "
          f"partials root; found {[str(p.relative_to(ROOT)) for p in holders]}")
    check(not str(PARTIALS).startswith(str(TPL)),
          "the partials root must be a SIBLING of templates/project/, or every "
          "clone gets the partial stamped in as an orphan file")
    for rel in SURFACES:
        src = TPL / f"{rel}.j2"
        check(INCLUDE in src.read_text(),
              f"{rel}.j2 must pull the preamble in with {INCLUDE}")


def _one_canonical_outbound_text() -> None:
    holders = [p for p in (ROOT / "cs").rglob("*")
               if p.is_file() and p.suffix in (".j2", ".py", ".md")
               and OUTBOUND_MARK in p.read_text(errors="replace")]
    check(holders == [PARTIALS / "outbound-fact-sourcing.md.j2"],
          f"the outbound-fact-sourcing marker must exist EXACTLY once in the "
          f"kernel, in the partials root; found "
          f"{[str(p.relative_to(ROOT)) for p in holders]}")
    prose_holders = [p for p in (ROOT / "cs").rglob("*")
                      if p.is_file() and p.suffix in (".j2", ".py", ".md")
                      and OUTBOUND_PROSE_MARK in p.read_text(errors="replace")]
    check(prose_holders == [PARTIALS / "outbound-fact-sourcing.md.j2"],
          f"the outbound-fact-sourcing PROSE must exist EXACTLY once in the "
          f"kernel, in the partials root — a fourth surface can paste the "
          f"rule's text without the HTML comment and still evade the marker "
          f"check above; found "
          f"{[str(p.relative_to(ROOT)) for p in prose_holders]}")
    for rel in OUTBOUND_SURFACES:
        src = TPL / f"{rel}.j2"
        check(OUTBOUND_INCLUDE in src.read_text(),
              f"{rel}.j2 must pull outbound-fact-sourcing in with "
              f"{OUTBOUND_INCLUDE}")


# ------------------------------------------------------------------ B + E

def _init_render() -> None:
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "acme-cs"
        ok, checksums = project_init.render_templates(dict(BASE), TPL, dest)
        check(ok, "cs init's own render_templates must succeed with the include")

        for rel in SURFACES:
            out = dest / rel
            check(out.exists(), f"cs init must stamp {rel}")
            text = out.read_text()
            check(PREAMBLE_MARK in text, f"{rel} must carry the preamble")
            check("{% include" not in text and "{{" not in text,
                  f"{rel} must carry no unrendered Jinja")

        check(not (dest / "desk-preamble.md").exists()
              and not (dest / "partials").exists(),
              "the partial itself is never stamped into a clone")
        check(not any("desk-preamble" in k for k in checksums),
              "and it is never entered in the checksum ledger")

        check(not (dest / "outbound-fact-sourcing.md").exists(),
              "the outbound-fact-sourcing partial itself is never stamped "
              "into a clone")
        check(not any("outbound-fact-sourcing" in k for k in checksums),
              "and it is never entered in the checksum ledger")

        # Single-source property for the outbound-fact-sourcing marker AND its
        # prose companion: each must land exactly once in each including
        # surface, and nowhere else in the rendered tree.
        outbound_hits: dict[Path, int] = {}
        outbound_prose_hits: dict[Path, int] = {}
        for path in dest.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(errors="replace")
            count = text.count(OUTBOUND_MARK)
            if count:
                outbound_hits[path.relative_to(dest)] = count
            prose_count = text.count(OUTBOUND_PROSE_MARK)
            if prose_count:
                outbound_prose_hits[path.relative_to(dest)] = prose_count
        for rel in OUTBOUND_SURFACES:
            check(outbound_hits.get(Path(rel)) == 1,
                  f"{rel} must carry the outbound-fact-sourcing marker "
                  f"exactly once, got {outbound_hits.get(Path(rel), 0)}")
            check(outbound_prose_hits.get(Path(rel)) == 1,
                  f"{rel} must carry the outbound-fact-sourcing PROSE mark "
                  f"exactly once, got {outbound_prose_hits.get(Path(rel), 0)}")
        check(set(outbound_hits) == {Path(rel) for rel in OUTBOUND_SURFACES},
              f"the outbound-fact-sourcing marker must appear only in "
              f"{OUTBOUND_SURFACES}, found it in "
              f"{sorted(str(k) for k in outbound_hits)}")
        check(set(outbound_prose_hits) == {Path(rel) for rel in OUTBOUND_SURFACES},
              f"the outbound-fact-sourcing PROSE mark must appear only in "
              f"{OUTBOUND_SURFACES}, found it in "
              f"{sorted(str(k) for k in outbound_prose_hits)}")

        # E — the whole rendered agent surface, from the DEFAULT manifest.
        for path in sorted((dest / ".claude").rglob("*")):
            if not path.is_file():
                continue
            hits = italian_hits(path.read_text(errors="replace"))
            check(not hits,
                  f"{path.relative_to(dest)} is stamped for every company in "
                  f"every market and carries Italian: {hits}")

        manifest = (dest / "manifest.toml").read_text()
        check(f'operator_voice = "{project_init.DEFAULT_OPERATOR_VOICE}"' in manifest,
              "the stamped manifest declares the voice the clone can edit")


def _kernel_digest_is_english() -> None:
    out = review.render({
        "drafts": [{"verdict": "ready", "to": "c@example.test",
                    "subject": "Invoice", "gmail_uid": "1", "engine_id": None}],
        "gmail_drafts": [{}], "engine_drafts": [], "tasks": [],
        "escalated": [{"email": "a@example.test", "owner": "you", "reason": "mine",
                       "days": 3, "escalated_on": "2026-08-20"}],
        "handled_out_of_band": [{"email": "b@example.test",
                                 "handled_on": "2026-08-19", "reason": "phoned"}],
        "campaigns": [{"campaign": "x", "counts": {}, "flagged": [],
                       "outcomes": {"engaged": 2}, "excluded": True}],
        "last_tick": ["2026-08-27T06:00:00Z acme-cs: tick end (exit 0)"],
    })
    hits = italian_hits(out)
    check(not hits, f"`cs review`'s digest is kernel code and reads English: {hits}\n{out}")


# ------------------------------------------------------------------ C + D

def _update_render() -> None:
    """A REAL `cs update`, against a clone frozen before either change."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CS_", "EMAIL_", "ENGINE_"))}

    with tempfile.TemporaryDirectory() as td:
        home = Path(td, "home"); home.mkdir()
        env["HOME"] = str(home)
        # Which `cs` will the subprocess actually import, and does that copy
        # SHIP the partial? Under tests/run.sh this is the freshly installed
        # package, and the answer is what gates the package-data glob: without
        # it the partial is absent from the wheel and every stamp fails. Run
        # from a source checkout the interpreter may hold some other clone's
        # installed kernel, which would silently test the wrong code — hence
        # the version comparison rather than a bare import check.
        probe = subprocess.run(
            [sys.executable, "-c",
             "import importlib.metadata as m;"
             "from cs.project_init import partials_root as r;"
             "print(m.version('cs-kernel'));"
             "print((r() / 'desk-preamble.md.j2').is_file())"],
            cwd=td, env=env, capture_output=True, text=True)
        installed = probe.stdout.split()
        this_version = tomllib.loads(
            (ROOT / "pyproject.toml").read_text())["project"]["version"]
        if probe.returncode == 0 and installed[:1] == [this_version]:
            check(installed[1:] == ["True"],
                  "the installed cs-kernel is THIS release and ships no "
                  "templates/partials/desk-preamble.md.j2 — the package-data "
                  "glob is missing and every `cs init` / `cs update` on a "
                  "clean install fails on the include")
        else:
            env["PYTHONPATH"] = str(ROOT)
            print(f"  note: this interpreter holds cs-kernel "
                  f"{installed[0] if installed else 'none'}, not {this_version} "
                  f"— running the update leg from the source tree (tests/run.sh "
                  f"runs it from the fresh venv, which is what gates packaging)")

        for label, declared in (("no voice declared", None),
                                ("voice declared", "Klingon, ceremonial")):
            clone = Path(td, f"clone-{len(label)}-{declared is not None}")
            clone.mkdir()
            # An EXISTING clone: init_data frozen before EITHER template-only
            # manifest key existed, exactly like both live clones on the
            # previous tag. Both must come off the manifest, not the freeze.
            frozen = {k: v for k, v in BASE.items()
                      if k not in ("operator_voice", "local_scripts_cron_denied")}
            (clone / "template-manifest.json").write_text(json.dumps({
                "template_version": "1", "init_data": frozen, "file_checksums": {},
            }))
            manifest = project_init.build_jinja_env(TPL).get_template(
                "manifest.toml.j2").render(
                    **{**BASE, "local_scripts_cron_denied": [SAMPLE_SCRIPT]})
            if declared:
                manifest = manifest.replace(
                    f'operator_voice = "{project_init.DEFAULT_OPERATOR_VOICE}"',
                    f'operator_voice = "{declared}"')
            (clone / "manifest.toml").write_text(manifest)

            proc = subprocess.run([sys.executable, "-m", "cs", "update"],
                                  cwd=clone, env=env, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True)
            out = proc.stdout + proc.stderr
            check(proc.returncode == 0,
                  f"[{label}] cs update must exit 0, got {proc.returncode}:\n{out}")
            for rel in SURFACES:
                check(f"failed to render {rel}" not in out,
                      f"[{label}] cs update must render {rel} — a loader-less "
                      f"environment breaks EVERY clone on the include:\n{out}")
                text = (clone / rel).read_text() if (clone / rel).exists() else ""
                check(PREAMBLE_MARK in text,
                      f"[{label}] cs update must stamp the preamble into {rel}")
                check((declared or project_init.DEFAULT_OPERATOR_VOICE) in text,
                      f"[{label}] the voice the MANIFEST declares must reach the "
                      f"stamp without re-running cs init ({rel})")

            # The same include-survives-`cs update` property, for the
            # outbound-fact-sourcing partial and its three including hosts —
            # `cs-review`/`cs-operator` are the preamble's hosts above,
            # CLAUDE.md and cs-campaign-tick are new here and untested on the
            # update path until now.
            for rel in OUTBOUND_SURFACES:
                check(f"failed to render {rel}" not in out,
                      f"[{label}] cs update must render {rel} — a loader-less "
                      f"environment breaks EVERY clone on the include:\n{out}")
                text = (clone / rel).read_text() if (clone / rel).exists() else ""
                check(OUTBOUND_MARK in text,
                      f"[{label}] cs update must stamp outbound-fact-sourcing "
                      f"into {rel}")
                check(OUTBOUND_PROSE_MARK in text,
                      f"[{label}] cs update must stamp the outbound-fact-sourcing "
                      f"PROSE into {rel}")

            # The same property for the other template-only key, on the file
            # where getting it wrong is a permission hole rather than a
            # greeting in the wrong language: a clone-local executable named
            # in `[local_scripts] cron_denied` must be denied in the stamped
            # wrapper, in every spelling, after a REAL `cs update` — with a
            # frozen init_data that predates the key entirely.
            wrapper = clone / "bin" / "cs_operator_cron.sh"
            check(wrapper.exists(),
                  f"[{label}] cs update must stamp bin/cs_operator_cron.sh:\n{out}")
            wrapper_text = wrapper.read_text() if wrapper.exists() else ""
            for form in (SAMPLE_SCRIPT, "./" + SAMPLE_SCRIPT):
                for interp in ("", ".venv/bin/python", ".venv/bin/python3",
                               "python", "python3", "bash", "sh"):
                    cmd = f"{interp} {form}" if interp else form
                    check(f'"Bash({cmd}:*)"' in wrapper_text,
                          f"[{label}] the executable the MANIFEST denies must be "
                          f"denied in the stamped wrapper as `{cmd}` — a spelling "
                          f"the tick can type and the deny list does not carry is "
                          f"an open door")


_one_canonical_text()
_one_canonical_outbound_text()
_init_render()
_kernel_digest_is_english()
_update_render()

if fails:
    print(f"test_stamped_surfaces: {fails} assertion(s) FAILED")
    sys.exit(1)
print("test_stamped_surfaces: all assertions passed")
