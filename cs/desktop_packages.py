"""Secret-free, workspace-bound desktop connector archives."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import zipfile


_GUIDE = """# Company operator connector

This candidate package has not been accepted in a real provider desktop app.
Install only in a client that supports this local package and review its tool
permissions. Company and engine privacy-policy metadata must be supplied before
publication or provider acceptance. No privacy-policy URL is invented here.
Tool results may include mail, tasks and company data sent to the chosen AI
provider. The selected remote engine also processes those data; review its
privacy terms and the provider terms before connecting. Exporting this archive does not install or connect that client.
ChatGPT Chat/Work support varies by account and surface; a local Codex plugin
installation does not prove Chat/Work support. An authenticated remote connector
may be required and is not provided by this package.

Start each conversation with operator_context and read operator://guidance.
Follow the returned company instructions and report missing or stale publication.
Use list_tasks, search_email, read_email, list_projects, read_project and
list_drafts for
bounded reads. ask_operator is read-only and can consult memory. prepare_reply
requires an explicit drafting request, source_email_id, thread_key, instruction
and an operation_id that stays unchanged when retrying the same request.
Draft preparation can incur engine API cost. No tool sends mail or approves it.
A client subscription does not pay engine API or direct kernel classifier costs.

The package contains a local STDIO client helper, not the Linux hosted daemon.
It contains the executable, not the workspace, descriptor or secrets.
The bound workspace must remain on this computer; moving or revoking it makes
this package unusable. Re-export after a binding change. The local connector
needs this computer awake and the selected engine reachable. Closing Desktop
is not evidence of revocation: use Desktop's revoke/sign-out action.
Do not share this profile-bound archive as a company-wide authorization grant.
"""


def _checked_path(path: Path, *, directory: bool = False) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Paths must be absolute without parent traversal")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Symlink paths are not allowed")
    if directory and not path.is_dir():
        raise ValueError("Directory does not exist")
    return path


def _json(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def export_packages(workspace: Path, runtime: Path, provider: str, output: Path) -> dict:
    """Export one candidate archive; caller verifies the workspace binding."""
    if provider not in {"claude", "chatgpt"}:
        raise ValueError("Provider must be claude or chatgpt")
    workspace = _checked_path(workspace, directory=True)
    runtime = _checked_path(runtime)
    output = _checked_path(output)
    _checked_path(output.parent, directory=True)
    if not runtime.is_file() or not os.access(runtime, os.X_OK):
        raise ValueError("Runtime must be an executable file")
    if output.suffix != (".mcpb" if provider == "claude" else ".zip"):
        raise ValueError("Output extension does not match provider")
    if output.exists():
        raise ValueError("Output already exists")
    if output == runtime or output.is_relative_to(workspace):
        raise ValueError("Export must be outside the operator workspace")
    if any("${" in str(path) or "\x00" in str(path) for path in (workspace, runtime, output)):
        raise ValueError("Paths cannot contain client variable substitutions")
    binary_name = "cs-operator.exe" if sys.platform == "win32" else "cs-operator"
    binary_path = "server/" + binary_name
    version = "0.0.0"
    identity = {
        "name": "company-operator",
        "version": version,
        "description": "Workspace-bound company operator tools; candidate package",
        "author": {"name": "Company operator"},
    }
    args = ["mcp", "--workspace", str(workspace)]
    if provider == "claude":
        manifest = {
            **identity,
            "manifest_version": "0.3",
            "server": {
                "type": "binary",
                "entry_point": binary_path,
                "mcp_config": {"command": "${__dirname}/" + binary_path, "args": args},
            },
            "compatibility": {"platforms": [sys.platform]},
            "tools_generated": True,
        }
        entries = {"manifest.json": _json(manifest)}
    else:
        entries = {
            "plugin.json": _json({
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                **identity,
            }),
            "mcp.json": _json({
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {"company-operator": {
                    "type": "stdio", "command": "${PLUGIN_ROOT}/" + binary_path,
                    "args": args,
                }},
            }),
        }
    entries["README.md"] = _GUIDE.encode()
    runtime_bytes = runtime.read_bytes()
    entries[binary_path] = runtime_bytes
    created = False
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, "wb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in sorted(entries.items()):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | (0o755 if name == binary_path else 0o644)) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    return {
        "artifact": str(output), "provider": provider, "acceptance": "unverified",
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "runtime_sha256": hashlib.sha256(runtime_bytes).hexdigest(),
    }
