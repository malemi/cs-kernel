"""Prepare per-clone observability packages without activating installed code."""

from __future__ import annotations

import argparse
import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

COMMON = ("config.py", "manifest.py", "config_report.py")
M2_FILES = (
    "cli.py",
    "worker_llm.py",
    "operator_recovery.py",
    "operator_workset.py",
    "draft_lifecycle.py",
    "gmail_drafts.py",
    "interactive_draft.py",
    "review_draft.py",
    "send_completion.py",
)
OBSERVERS = {"diagnostic_emit", "emit", "maintain", "active"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def manifest(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError("Symlink in package")
        if not path.is_file() and not path.is_dir():
            raise ValueError("Nonregular package entry")
        if path.is_file():
            result[str(path.relative_to(root))] = {
                "sha256": digest(path.read_bytes()),
                "mode": stat.S_IMODE(path.stat().st_mode),
            }
    return result


def exact_patch(source, before, after):
    delta = "".join(
        difflib.unified_diff(
            before.splitlines(True), after.splitlines(True), fromfile="old", tofile="new"
        )
    )
    if not delta:
        return source
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "target.py"
        target.write_text(source)
        run = subprocess.run(
            ["patch", "--batch", "--fuzz=0", "--no-backup-if-mismatch", str(target)],
            input=delta,
            text=True,
            capture_output=True,
        )
        if run.returncode:
            raise ValueError(
                "Exact observation patch refused: "
                + run.stdout.replace(str(target), "target")[:1200]
            )
        return target.read_text()


def definition(source, name):
    found = [n for n in ast.parse(source).body if getattr(n, "name", None) == name]
    if len(found) != 1:
        raise ValueError("Ambiguous definition: " + name)
    return found[0]


def replace_node(source, old, replacement):
    lines = source.splitlines(True)
    return (
        "".join(lines[: old.lineno - 1])
        + replacement.rstrip()
        + "\n"
        + "".join(lines[old.end_lineno :])
    )


def rpc_class(source, reviewed, reference=None):
    old, new = definition(source, "EngineClient"), definition(reviewed, "EngineClient")
    changed = {"__init__", "__aenter__", "call"}
    expected = definition(reference if reference is not None else source, "EngineClient")
    for name in changed:
        left = next(n for n in old.body if getattr(n, "name", None) == name)
        known = next(n for n in expected.body if getattr(n, "name", None) == name)
        if ast.dump(left, include_attributes=False) != ast.dump(known, include_attributes=False):
            raise ValueError("Unknown original EngineClient transport")

    def stable(node):
        value = copy.deepcopy(node)
        value.body = [n for n in value.body if getattr(n, "name", None) not in changed]
        return ast.dump(value, include_attributes=False)

    if stable(old) != stable(new):
        raise ValueError("Unreviewed EngineClient business difference")
    for name in changed:
        left = next(n for n in old.body if getattr(n, "name", None) == name)
        right = next(n for n in new.body if getattr(n, "name", None) == name)
        if ast.dump(left.args, include_attributes=False) != ast.dump(
            right.args, include_attributes=False
        ):
            raise ValueError("EngineClient signature changed")
    result = replace_node(source, old, ast.get_source_segment(reviewed, new))
    if "import time\n" not in result:
        if result.count("import sys\n") != 1:
            raise ValueError("Unknown RPC import boundary")
        result = result.replace("import sys\n", "import sys\nimport time\n", 1)
    return result


def safe_observation(node):
    names = OBSERVERS | {
        "len",
        "error_metadata",
        "error_reason",
        "current_context",
        "diagnostic_context",
    }
    for value in ast.walk(node):
        if not isinstance(value, ast.Call):
            continue
        function = value.func
        if isinstance(function, ast.Name) and function.id in names:
            continue
        if isinstance(function, ast.Attribute) and function.attr == "get":
            continue
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and (function.value.id, function.attr)
            in {("json", "loads"), ("json", "dumps"), ("secrets", "token_hex")}
        ):
            continue
        return False
    return True


class StripObservations(ast.NodeTransformer):
    def visit_ImportFrom(self, node):
        if (node.module or "").startswith(("observability", "logs_cli", "monitor_cli")):
            return None
        if node.module is None:
            names = [n for n in node.names if n.name not in {"logs_cli", "monitor_cli"}]
            if not names:
                return None
            node.names = names
        return node

    def visit_FunctionDef(self, node):
        node.decorator_list = [
            d
            for d in node.decorator_list
            if not (
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Name)
                and d.func.id == "_diagnostic_observe"
            )
        ]
        return self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Name) and fn.id in OBSERVERS and safe_observation(node):
                return None
            if (
                isinstance(fn, ast.Attribute)
                and isinstance(fn.value, ast.Name)
                and fn.value.id in {"logs_cli", "monitor_cli"}
            ):
                return None
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if any(
            isinstance(n, ast.Subscript)
            and isinstance(n.value, ast.Name)
            and n.value.id == "env"
            and isinstance(n.slice, ast.Constant)
            and n.slice.value == "CS_DIAGNOSTIC_CONTEXT"
            for n in node.targets
        ) and safe_observation(node):
            return None
        return self.generic_visit(node)

    def visit_With(self, node):
        if all(
            isinstance(i.context_expr, ast.Call)
            and isinstance(i.context_expr.func, ast.Name)
            and i.context_expr.func.id == "diagnostic_context"
            for i in node.items
        ):
            return [out for n in node.body for out in self._visit_list(n)]
        return self.generic_visit(node)

    def _visit_list(self, node):
        value = self.visit(node)
        return value if isinstance(value, list) else [] if value is None else [value]

    def visit_Try(self, node):
        diagnostic = (
            not node.orelse
            and not node.finalbody
            and len(node.handlers) == 1
            and isinstance(node.handlers[0].type, ast.Name)
            and node.handlers[0].type.id == "BaseException"
            and len(node.handlers[0].body) == 2
            and isinstance(node.handlers[0].body[0], ast.Expr)
            and isinstance(node.handlers[0].body[0].value, ast.Call)
            and isinstance(node.handlers[0].body[0].value.func, ast.Name)
            and node.handlers[0].body[0].value.func.id == "diagnostic_emit"
            and safe_observation(node.handlers[0].body[0])
            and isinstance(node.handlers[0].body[1], ast.Raise)
            and node.handlers[0].body[1].exc is None
        )
        result = self.generic_visit(node)
        return result.body if diagnostic else result

    def visit_For(self, node):
        result = self.generic_visit(node)
        if (
            not result.body
            and isinstance(node.target, ast.Name)
            and node.target.id in {"selected_row", "deferred_row", "held_row"}
        ):
            return None
        return result

    def visit_If(self, node):
        if (
            isinstance(node.test, ast.Compare)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.List)
            and [n.value for n in node.test.comparators[0].elts if isinstance(n, ast.Constant)]
            == ["monitor"]
            and any(isinstance(n, ast.ImportFrom) and n.module == "monitor_cli" for n in node.body)
        ):
            return None
        result = self.generic_visit(node)
        if not result.body and not result.orelse:
            return None
        return result


def business_equal(before, after):
    stripped = StripObservations().visit(ast.parse(after))
    return ast.dump(ast.parse(before), include_attributes=False) == ast.dump(
        stripped, include_attributes=False
    )


def add_logs_registration(source):
    anchor = "    project_memory_mod.add_subparsers(sub)\n"
    if source.count(anchor) != 1 or "logs_cli.add_subparsers(sub)" in source:
        raise ValueError("Unknown CLI parser registration boundary")
    return source.replace(
        anchor, anchor + "    from . import logs_cli\n    logs_cli.add_subparsers(sub)\n", 1
    )


def add_notice_helper(source, reviewed):
    before = ast.parse(source)
    after = ast.parse(reviewed)
    additions = [
        n
        for n in after.body
        if getattr(n, "name", None) not in {getattr(x, "name", None) for x in before.body}
        and isinstance(n, (ast.FunctionDef, ast.ClassDef))
    ]
    if not additions:
        return source
    if any(n.name != "send_operational_notice" for n in additions):
        raise ValueError("Unknown SMTP helper addition")
    result = source
    for node in additions:
        result += "\n\n" + ast.get_source_segment(reviewed, node) + "\n"
    return result


def prepare_package(baseline, output, before_m2, reviewed, m1_reference):
    original = manifest(baseline)
    original_directories = {
        str(p.relative_to(baseline)): stat.S_IMODE(p.stat().st_mode)
        for p in [baseline, *sorted(baseline.rglob("*"))]
        if p.is_dir() and "__pycache__" not in p.parts
    }
    source_manifest = manifest(reviewed)
    if output.exists() or any(
        output.resolve().is_relative_to(root.resolve())
        or root.resolve().is_relative_to(output.resolve())
        for root in (baseline, reviewed, m1_reference)
    ):
        raise ValueError("Candidate output must be new and outside all source packages")
    shutil.copytree(
        baseline,
        output,
        copy_function=shutil.copy2,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    edits = {}
    patches = {}
    for name in COMMON:
        old = (output / name).read_text()
        reference = (m1_reference / name).read_text()
        if old != reference:
            raise ValueError("Unknown pre-M1 configuration family: " + name)
        new = exact_patch(old, reference, (reviewed / name).read_text())
        (output / name).write_text(new)
        edits[name] = {
            "kind": "reviewed-M1-configuration",
            "before": digest(old.encode()),
            "after": digest(new.encode()),
        }
        patches[name] = "".join(
            difflib.unified_diff(
                old.splitlines(True), new.splitlines(True), fromfile="a/" + name, tofile="b/" + name
            )
        )
    old = (output / "rpc.py").read_text()
    new = rpc_class(old, (reviewed / "rpc.py").read_text(), (m1_reference / "rpc.py").read_text())
    edits["rpc.py"] = {
        "kind": "reviewed-EngineClient-only",
        "before": digest(old.encode()),
        "after": digest(new.encode()),
    }
    (output / "rpc.py").write_text(new)
    patches["rpc.py"] = "".join(
        difflib.unified_diff(
            old.splitlines(True), new.splitlines(True), fromfile="a/rpc.py", tofile="b/rpc.py"
        )
    )
    for name in M2_FILES:
        if not (output / name).exists():
            continue
        original_source = (output / name).read_text()
        old = add_logs_registration(original_source) if name == "cli.py" else original_source
        after = (reviewed / name).read_text()
        terminal = "    from .observability_producers import emit as diagnostic_emit\n    diagnostic_emit(settings, 'provider', 'unknown-effect', reason='unknown', draft_id=draft_id, root_id=key)\n"
        if name == "cli.py":
            if after.count(terminal) != 1:
                raise ValueError("Unknown send uncertainty observation")
            after = after.replace(terminal, "", 1)
        new = exact_patch(old, (before_m2 / name).read_text(), after)
        if name == "cli.py":
            fn = definition(new, "cmd_draft_send")
            targets = [
                n
                for n in fn.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "states" for t in n.targets)
            ]
            if len(targets) != 1:
                raise ValueError("Unknown original send uncertainty boundary")
            lines = new.splitlines(True)
            lines.insert(targets[0].lineno - 1, terminal)
            new = "".join(lines)
        if not business_equal(original_source, new):
            raise ValueError("Business AST changed: " + name)
        (output / name).write_text(new)
        edits[name] = {
            "kind": "reviewed-M2-observation-only",
            "before": digest(original_source.encode()),
            "after": digest(new.encode()),
            "business_ast_equal": True,
        }
        patches[name] = "".join(
            difflib.unified_diff(
                original_source.splitlines(True),
                new.splitlines(True),
                fromfile="a/" + name,
                tofile="b/" + name,
            )
        )
    new_files = []
    for path in sorted(reviewed.glob("*.py")):
        if not (path.name.startswith(("observability", "monitor")) or path.name == "logs_cli.py"):
            continue
        target = output / path.name
        if target.exists():
            raise ValueError("Existing observer module would be overwritten")
        shutil.copy2(path, target)
        new_files.append(path.name)
    notice = output / "send_mail.py"
    if notice.exists():
        old = notice.read_text()
        new = add_notice_helper(old, (reviewed / "send_mail.py").read_text())
        if new != old:
            notice.write_text(new)
            edits["send_mail.py"] = {
                "kind": "new-operational-notice-only",
                "before": digest(old.encode()),
                "after": digest(new.encode()),
            }
            patches["send_mail.py"] = "".join(
                difflib.unified_diff(
                    old.splitlines(True),
                    new.splitlines(True),
                    fromfile="a/send_mail.py",
                    tofile="b/send_mail.py",
                )
            )
    result = manifest(output)
    untouched = set(original) - set(edits)
    if any(original[name] != result.get(name) for name in untouched):
        raise ValueError("Untouched baseline bytes or modes changed")
    if any(original[name]["mode"] != result[name]["mode"] for name in edits):
        raise ValueError("Existing file modes changed")
    for relative, mode in original_directories.items():
        if stat.S_IMODE((output / relative).stat().st_mode) != mode:
            raise ValueError("Package directory modes changed")
    if manifest(baseline) != original:
        raise ValueError("Installed baseline changed during preparation")
    before_files = output.parent / "before"
    before_files.mkdir(mode=0o700)
    for name in edits:
        shutil.copy2(baseline / name, before_files / name)
    if manifest(reviewed) != source_manifest:
        raise ValueError("Reviewed source changed during preparation; rerun after freeze")
    for path in output.rglob("*.py"):
        compile(path.read_bytes(), str(path), "exec")
    return {
        "baseline_manifest": original,
        "baseline_directory_modes": original_directories,
        "candidate_manifest": result,
        "edits": edits,
        "new_files": new_files,
        "untouched_files_verified": len(untouched),
        "reviewed_manifest": source_manifest,
        "patches": patches,
        "activated": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before-m2", type=Path, required=True)
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--m1-reference", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    args.output.parent.chmod(0o700)
    proof = prepare_package(
        args.baseline, args.output, args.before_m2, args.reviewed, args.m1_reference
    )
    target = args.output.parent / (args.output.name + "-proof.json")
    target.write_text(json.dumps(proof, indent=2) + "\n")
    target.chmod(0o600)
    print(
        json.dumps(
            {
                "candidate": str(args.output),
                "untouched_files_verified": proof["untouched_files_verified"],
                "activated": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
