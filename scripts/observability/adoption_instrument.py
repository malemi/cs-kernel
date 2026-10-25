"""Exact observation-only source transforms for preserved engine families."""

from __future__ import annotations

import ast
import difflib
from pathlib import Path
import subprocess
import tempfile


def insert_before(source: str, line: int, content: str) -> str:
    lines = source.splitlines(keepends=True)
    lines.insert(line - 1, content)
    return "".join(lines)


def decorator(source: str, class_name: str | None, name: str, expression: str) -> str:
    tree = ast.parse(source)
    scope = (
        tree
        if class_name is None
        else next(n for n in tree.body if getattr(n, "name", None) == class_name)
    )
    functions = [
        n
        for n in scope.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    ]
    if len(functions) != 1:
        raise ValueError("Ambiguous instrumentation target")
    fn = functions[0]
    indent = " " * fn.col_offset
    return insert_before(source, fn.lineno, indent + "@" + expression + "\n")


def patch_m2(source: str, relative: str, before: Path, reviewed: Path) -> str:
    """All hunks must apply exactly, without fuzz; reject partial application."""
    original = (before / relative).read_text()
    after = (reviewed / relative).read_text()
    delta = "".join(
        difflib.unified_diff(
            original.splitlines(True), after.splitlines(True), fromfile="old", tofile="new"
        )
    )
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "target.py"
        target.write_text(source)
        result = subprocess.run(
            ["patch", "--batch", "--fuzz=0", str(target)],
            input=delta,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise ValueError(
                "Exact M2 patch refused: "
                + relative
                + ": "
                + result.stdout.replace(str(target), "target.py")[:1200]
            )
        return target.read_text()


def peer_setup(source: str) -> str:
    """Observe the older handler without adopting the newer business algorithm."""
    source = source.replace(
        "import logging\n",
        "import logging\nfrom zylch.observability_producers import observed, failure\n",
        1,
    )
    source = decorator(
        source, None, "sync_run", 'observed("acquisition", "sync.run", private=True)'
    )
    fn = next(n for n in ast.parse(source).body if getattr(n, "name", None) == "sync_run")
    handlers = [
        h
        for n in fn.body
        if isinstance(n, ast.Try)
        for h in n.handlers
        if isinstance(h.type, ast.Name) and h.type.id == "Exception"
    ]
    if len(handlers) != 1 or handlers[0].name != "e":
        raise ValueError("Unknown legacy sync error boundary")
    return insert_before(
        source, handlers[0].body[0].lineno, '        failure("acquisition", e, method="sync.run")\n'
    )


def instrument_ws(source: str) -> str:
    source = source.replace(
        "import asyncio\n",
        "import asyncio\nfrom zylch.observability_producers import observed, observe, failure\n",
        1,
    )
    replacements = {
        '        logger.warning(f"[ws] handshake rejected (401): {e}")': '        failure("authority", e, reason="auth", method="engine.handshake")\n        logger.warning("[ws] handshake rejected (401)")',
        '        logger.warning(f"[ws] handshake forbidden (403): {e}")': '        failure("authority", e, reason="auth", method="engine.handshake")\n        logger.warning("[ws] handshake forbidden (403)")',
        '    logger.info(f"[ws] client connected uid={uid} email={email!r}")': '    observe("context", "start", method="engine.connection", reason="none")\n    logger.info("[ws] client connected")',
        '        logger.warning(f"[ws] connection error uid={uid}: {type(e).__name__}: {e}")': '        failure("context", e, method="engine.connection")\n        logger.warning("[ws] connection failed")',
        '        logger.info(f"[ws] client disconnected uid={uid}")': '        observe("context", "result", method="engine.connection", reason="none")\n        logger.info("[ws] client disconnected")',
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise ValueError("Unknown WebSocket observation boundary")
        source = source.replace(old, new, 1)
    return decorator(source, None, "serve_ws", 'observed("launch", "engine.ws")')


def instrument_gmail(source: str) -> str:
    source = source.replace(
        "import logging\n",
        "from zylch.observability_producers import observed, observe, failure\nimport logging\n",
        1,
    )
    for cls, stage, method in (
        ("CreateDraftTool", "persistence", "create_draft"),
        ("UpdateDraftTool", "persistence", "update_draft"),
        ("SendDraftTool", "provider", "send_draft"),
    ):
        source = decorator(source, cls, "execute", f'observed("{stage}", "{method}", private=True)')
    tree = ast.parse(source)
    additions = []
    expected = {
        "Failed to create draft": 'failure("persistence", e)',
        "Failed to update draft": 'failure("persistence", e)',
        "[send_draft] unresolvable handle": 'failure("provider", e, draft_id=draft_id, reason="incomplete-input", effect_certainty="none")',
        "Failed to prepare draft for sending": 'failure("provider", e, draft_id=draft_id, effect_certainty="none")',
        "Failed to prepare claimed draft for sending": 'failure("provider", e, draft_id=draft_id, effect_certainty="none")',
        "Failed to send draft": 'failure("provider", e, draft_id=draft_id, effect_certainty="unknown" if delivery_is_uncertain(e) else "none")',
        "[send_draft] mark_draft_sent failed after delivery": 'failure("persistence", e)',
        "[send_draft] persist failed (non-blocking)": 'failure("persistence", e)',
    }
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.name != "e":
            continue
        for statement in node.body:
            if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
                continue
            call = statement.value
            if (
                not isinstance(call.func, ast.Attribute)
                or not isinstance(call.func.value, ast.Name)
                or call.func.value.id != "logger"
                or not call.args
            ):
                continue
            content = "".join(
                n.value
                for n in ast.walk(call.args[0])
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            )
            for prefix, observation in expected.items():
                if content.startswith(prefix):
                    if prefix in found:
                        raise ValueError("Ambiguous Gmail error boundary")
                    found.add(prefix)
                    additions.append(
                        (statement.lineno, " " * statement.col_offset + observation + "\n")
                    )
    if found != set(expected):
        raise ValueError("Missing Gmail boundary: " + str(set(expected) - found))
    cls = next(n for n in tree.body if getattr(n, "name", None) == "SendDraftTool")
    fn = next(n for n in cls.body if getattr(n, "name", None) == "execute")
    for target, observation, before in (
        ("sent_message", 'observe("provider", "start", draft_id=draft_id, reason="none")', True),
        (
            "sent_id",
            'observe("provider", "accepted", draft_id=draft_id, provider_id=sent_id, reason="none", effect_certainty="accepted")',
            False,
        ),
    ):
        matches = [
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == target for t in n.targets)
        ]
        if len(matches) != 1:
            raise ValueError("Ambiguous Gmail transport boundary")
        node = matches[0]
        additions.append(
            (
                node.lineno if before else node.end_lineno + 1,
                " " * node.col_offset + observation + "\n",
            )
        )
    for line, text in sorted(additions, reverse=True):
        source = insert_before(source, line, text)
    return source


def instrument_dispatch(source: str, reviewed: Path) -> str:
    tree = ast.parse(source)
    original = next(n for n in tree.body if getattr(n, "name", None) == "dispatch_raw")
    handlers = [
        h
        for n in original.body
        if isinstance(n, ast.Try)
        for h in n.handlers
        if isinstance(h.type, ast.Name) and h.type.id == "Exception"
    ]
    if len(handlers) != 1 or handlers[0].name != "e":
        raise ValueError("Unknown dispatch error boundary")
    source = insert_before(
        source,
        handlers[0].body[0].lineno,
        '        from zylch.observability_producers import failure\n        failure("rpc", e, method=method, rpc_id=req_id)\n',
    )
    source = source.replace("async def dispatch_raw(", "async def _dispatch_raw(", 1)
    current = (reviewed / "rpc/dispatch.py").read_text()
    wrapper = next(n for n in ast.parse(current).body if getattr(n, "name", None) == "dispatch_raw")
    source += (
        "\n\n" + "\n".join(current.splitlines()[wrapper.lineno - 1 : wrapper.end_lineno]) + "\n"
    )
    return source


def instrument_methods(source: str, reviewed: Path) -> str:
    fn = next(
        n for n in ast.parse(source).body if getattr(n, "name", None) == "system_capabilities"
    )
    returns = [n for n in fn.body if isinstance(n, ast.Return)]
    if len(returns) != 1 or not isinstance(returns[0].value, ast.Dict):
        raise ValueError("Unknown capability shape")
    mapping = returns[0].value
    if any(isinstance(k, ast.Constant) and k.value == "observability" for k in mapping.keys):
        raise ValueError("Runtime already declares observability")
    lines = source.splitlines(keepends=True)
    line = lines[mapping.lineno - 1]
    lines[mapping.lineno - 1] = (
        line[: mapping.col_offset + 1] + '"observability": 1, ' + line[mapping.col_offset + 1 :]
    )
    source = "".join(lines)
    current = (reviewed / "rpc/methods.py").read_text()
    source += (
        "\n"
        + current[
            current.index("from zylch.rpc.diagnostics import METHODS as _DIAGNOSTIC_METHODS") :
        ]
    )
    return source
