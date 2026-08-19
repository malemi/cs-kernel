"""Gate: `cs init` writes ~/.<slug>-cs/.env itself — the operator types one
password, not one file.

Before this feature, README Step 3 told the operator to mkdir/cp/hand-edit a
dotenv whose values the wizard ALREADY knew (CS_ACCOUNTS from the accounts
registry, FIREBASE_WEB_API_KEY from the Step-0 descriptor) — the worst step
of the walkthrough for a non-technical operator. Guards, on the REAL
`.env.example.j2` rendered with `cs init`'s own jinja options (StrictUndefined):

1. a fresh run fills EMAIL_PASSWORD (getpass), FIREBASE_WEB_API_KEY and
   CS_ACCOUNTS on the template's own anchor lines, lands the file mode 0600
   in a 0700 state dir REGARDLESS of umask, and leaves the rendered
   .env.example itself untouched (it stays the empty reference copy);
2. an existing ~/.<slug>-cs/.env is operator-owned: byte-identical after a
   second run, and the password prompt is never even shown;
3. EOF on the password prompt (closed stdin — the v0.5.2 contract) writes
   the file with EMAIL_PASSWORD blank and prints the decision, no crash.
"""
from __future__ import annotations

import contextlib
import io
import os
import stat
import sys
import tempfile
from pathlib import Path

import jinja2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cs import project_init as pi  # noqa: E402

CONFIG = {
    "company_prog_name": "acme-cs",
    "company_slug": "acme",
    "email_address": "support@acme.example",
    "firebase_web_api_key": "AIzaTESTKEY123",
    "platform_env_path": "",
    "accounts": {"support": "uid-support-1", "press": "uid-press-2"},
    "crm_adapter": "none",
    "crm_shopify": None,
    "sms_enabled": False,
    "sms_proxy_base": "",
    "cs_triage_mode": "draft",
    "drive_scope": "",
}


def render_example(dest_dir: Path) -> str:
    template_dir = ROOT / "cs" / "templates" / "project"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined,
    )
    content = env.get_template(".env.example.j2").render(**CONFIG)
    (dest_dir / ".env.example").write_text(content, encoding="utf-8")
    return content


def env_value(text: str, key: str) -> str:
    hits = [
        ln.split("=", 1)[1]
        for ln in text.splitlines()
        if ln.startswith(f"{key}=")
    ]
    assert len(hits) == 1, f"{key}: expected exactly one uncommented line, got {len(hits)}"
    return hits[0]


def with_password(answer):
    def fake(prompt=""):
        if isinstance(answer, BaseException):
            raise answer
        return answer

    return fake


def main() -> None:
    old_umask = os.umask(0o000)  # permissive on purpose: the mode must not depend on it
    old_getpass = pi.getpass.getpass
    old_home = os.environ.get("HOME")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            dest = Path(tmp) / "acme-cs"
            home.mkdir()
            dest.mkdir()
            os.environ["HOME"] = str(home)
            example_before = render_example(dest)

            # 1. fresh run: anchors filled, modes enforced, example untouched
            pi.getpass.getpass = with_password("s3cret pass")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                pi.write_state_env(CONFIG, dest)
            env_path = home / ".acme-cs" / ".env"
            assert env_path.exists(), "fresh run did not write ~/.acme-cs/.env"
            text = env_path.read_text(encoding="utf-8")
            assert env_value(text, "EMAIL_PASSWORD") == "s3cret pass"
            assert env_value(text, "FIREBASE_WEB_API_KEY") == "AIzaTESTKEY123"
            assert env_value(text, "CS_ACCOUNTS") == "support:uid-support-1,press:uid-press-2"
            mode = stat.S_IMODE(env_path.stat().st_mode)
            assert mode == 0o600, f".env mode is {oct(mode)}, expected 0600 (umask was 000)"
            dir_mode = stat.S_IMODE(env_path.parent.stat().st_mode)
            assert dir_mode == 0o700, f"state dir mode is {oct(dir_mode)}, expected 0700"
            example_after = (dest / ".env.example").read_text(encoding="utf-8")
            assert example_after == example_before, ".env.example was modified by the writer"
            assert env_value(example_after, "EMAIL_PASSWORD") == "", (
                ".env.example must stay the empty reference copy"
            )
            assert "mode 0600" in out.getvalue()

            # 2. existing file is operator-owned: untouched, no prompt shown
            pi.getpass.getpass = with_password(AssertionError("prompted despite existing .env"))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                pi.write_state_env(CONFIG, dest)
            assert env_path.read_text(encoding="utf-8") == text, "existing .env was rewritten"
            assert "Kept existing" in out.getvalue()

            # 3. EOF on the prompt: blank password, decision printed, no crash
            env_path.unlink()
            pi.getpass.getpass = with_password(EOFError())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                pi.write_state_env(CONFIG, dest)
            text = env_path.read_text(encoding="utf-8")
            assert env_value(text, "EMAIL_PASSWORD") == ""
            assert env_value(text, "CS_ACCOUNTS") == "support:uid-support-1,press:uid-press-2"
            assert "EMAIL_PASSWORD blank" in out.getvalue()
    finally:
        os.umask(old_umask)
        pi.getpass.getpass = old_getpass
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home

    print("test_state_env: all assertions passed")


if __name__ == "__main__":
    main()
