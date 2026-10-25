"""Reject unreviewed business changes in an observability-only runtime candidate."""

from __future__ import annotations

import ast
import copy


class StripObservations(ast.NodeTransformer):
    """Compare business ASTs while removing only the declared diagnostic seams."""

    def __init__(self, original: ast.Module):
        self.logging_function = next(
            (n for n in original.body if getattr(n, "name", None) == "_setup_log_file"), None
        )

    def visit_ImportFrom(self, node):
        if (node.module or "").startswith(("zylch.observability", "zylch.rpc.diagnostics")):
            return None
        return node

    def visit_Expr(self, node):
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in {"observe", "failure"}
        ):
            return None
        return self.generic_visit(node)

    def visit_Call(self, node):
        node = self.generic_visit(node)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "copied"
            and len(node.args) == 1
            and not node.keywords
        ):
            return node.args[0]
        return node

    def visit_For(self, node):
        if (
            isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Attribute)
            and isinstance(node.iter.func.value, ast.Name)
            and node.iter.func.value.id == "_DIAGNOSTIC_METHODS"
        ):
            return None
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        if node.name == "dispatch_raw" and any(
            isinstance(n, ast.ImportFrom) and n.module == "zylch.observability_context"
            for n in ast.walk(node)
        ):
            return None
        if node.name == "_dispatch_raw":
            node.name = "dispatch_raw"
        return self.visit_FunctionDef(node)

    def visit_FunctionDef(self, node):
        if node.name == "_setup_log_file" and self.logging_function is not None:
            return copy.deepcopy(self.logging_function)
        node.decorator_list = [
            d
            for d in node.decorator_list
            if not (
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Name)
                and d.func.id in {"observed", "observed_sync"}
            )
        ]
        node = self.generic_visit(node)
        if node.name == "system_capabilities":
            for result in node.body:
                if isinstance(result, ast.Return) and isinstance(result.value, ast.Dict):
                    pairs = [
                        (k, v)
                        for k, v in zip(result.value.keys, result.value.values)
                        if not (isinstance(k, ast.Constant) and k.value == "observability")
                    ]
                    result.value.keys = [p[0] for p in pairs]
                    result.value.values = [p[1] for p in pairs]
        return node

    def visit_Try(self, node):
        observed_handlers = [
            h
            for h in node.handlers
            if len(h.body) == 2
            and isinstance(h.body[0], ast.Expr)
            and isinstance(h.body[0].value, ast.Call)
            and isinstance(h.body[0].value.func, ast.Name)
            and h.body[0].value.func.id == "failure"
            and isinstance(h.body[1], ast.Raise)
        ]
        node = self.generic_visit(node)
        node.handlers = [h for h in node.handlers if h not in observed_handlers]
        return node


def business_equal(
    original: str,
    candidate: str,
    *,
    logger_redactions: bool = False,
    approved_logging: str | None = None,
) -> bool:
    before = ast.parse(original)
    old_logger = [n for n in before.body if getattr(n, "name", None) == "_setup_log_file"]
    new_logger = [
        n for n in ast.parse(candidate).body if getattr(n, "name", None) == "_setup_log_file"
    ]
    if (
        old_logger
        and new_logger
        and ast.dump(old_logger[0], include_attributes=False)
        != ast.dump(new_logger[0], include_attributes=False)
    ):
        if approved_logging is None or ast.dump(
            new_logger[0], include_attributes=False
        ) != ast.dump(ast.parse(approved_logging).body[0], include_attributes=False):
            return False
    after = StripObservations(before).visit(ast.parse(candidate))
    if logger_redactions:
        # Restore only known, reviewed metadata redactions to their original AST.
        before_logs = [
            n
            for n in ast.walk(before)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "logger"
        ]
        after_logs = [
            n
            for n in ast.walk(after)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "logger"
        ]
        if len(before_logs) != len(after_logs):
            return False
        for a, b in zip(before_logs, after_logs):
            if ast.dump(a, include_attributes=False) != ast.dump(b, include_attributes=False):
                if (
                    b.func.attr not in {"warning", "info"}
                    or not b.args
                    or not isinstance(b.args[0], ast.Constant)
                    or b.args[0].value
                    not in {
                        "[ws] handshake rejected (401)",
                        "[ws] handshake forbidden (403)",
                        "[ws] client connected",
                        "[ws] connection failed",
                        "[ws] client disconnected",
                    }
                ):
                    return False
                b.args = copy.deepcopy(a.args)
                b.keywords = copy.deepcopy(a.keywords)
    return ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False)
