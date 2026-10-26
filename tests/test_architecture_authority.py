"""Render the standing-authority contract for both architecture shapes."""
import sys
from pathlib import Path

from cs.project_init import build_jinja_env
from jinja2 import meta

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "cs/templates/project"
EXPECTED = "- **Effective standing instructions** are read with `cs standing-instructions`:\n  the authenticated engine supplies this mailbox's identity and company procedures,\n  including their authority, revisions and verified hashes. Failed reads hold\n  drafting; other local company notes cannot replace these published rules.\n  In `legacy` mode, the engine's `operator-instructions` company project is a\n  derived copy compiled from [company/customer-service-playbook.md](../company/customer-service-playbook.md)\n  and [company/mailbox-identity.md](../company/mailbox-identity.md) through the\n  explicit `cs instructions --commit` workflow. Other company mailboxes without\n  their own clone use `company/mailboxes/<email>.md` for identity. After explicit\n  human confirmation in Desktop, `managed` company records become canonical;\n  local source files are preserved and must not overwrite those records.\n  Conversational teaching invokes `cs-instructions`, which checks authority before\n  editing and routes managed changes to human confirmation in Desktop. Legacy\n  empty or absent compiler inputs do not clear published documents; the legacy\n  workflow uses nonempty factual replacements when retiring the last rule.\n"


def verify(source):
    env = build_jinja_env(TPL)
    variables = meta.find_undeclared_variables(env.parse(source))
    context = {name: "neutral" for name in variables}
    context.update(accounts={"support": "UID123"}, accounts_default="support",
                   crm_adapter="none", producer_adapter="none", sms_enabled=False,
                   founder_sweep_enabled=False, platform_env_path="")
    for shape in ("generic", "as-built"):
        rendered = env.from_string(source).render(**{**context, "repo_docs_shape": shape})
        section = rendered.split("## Outside this repo (referenced, never stamped)\n\n", 1)[1]
        authority = section.split("- **Secrets**", 1)[0]
        if authority != EXPECTED:
            raise AssertionError(f"{shape}: standing-authority paragraph differs")
        if ("mother clone" in rendered) != (shape == "generic"):
            raise AssertionError(f"{shape}: architecture shape differs")
    print("OK: generic and as-built renders preserve managed/legacy standing authority")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else TPL / "docs/ARCHITECTURE.md.j2"
    verify(source.read_text())
