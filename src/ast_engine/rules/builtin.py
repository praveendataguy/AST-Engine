"""Built-in rules shipped with AST Engine."""
from __future__ import annotations

import ast

from ast_engine.models import Severity
from ast_engine.rules.base import Rule, register

_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


@register
class BareExcept(Rule):
    code = "AST001"
    name = "bare-except"
    description = "Bare `except:` also catches SystemExit and KeyboardInterrupt."

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.report(node, "Bare `except:`; catch a specific exception (or `Exception`)")
        self.generic_visit(node)


@register
class MutableDefault(Rule):
    code = "AST002"
    name = "mutable-default"
    description = "Mutable default arguments are shared between calls."
    _MUTABLE_CALLS = {"list", "dict", "set"}

    def _check(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> None:
        defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
        for default in defaults:
            mutable = isinstance(default, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp))
            if isinstance(default, ast.Call) and isinstance(default.func, ast.Name):
                mutable = mutable or default.func.id in self._MUTABLE_CALLS
            if mutable:
                self.report(default, "Mutable default argument; use `None` and create the value inside")
        self.generic_visit(node)

    visit_FunctionDef = visit_AsyncFunctionDef = visit_Lambda = _check


@register
class UnusedImport(Rule):
    code = "AST003"
    name = "unused-import"
    description = "Imported name is never used in the module."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.imports: dict[str, ast.AST] = {}
        self.used: set[str] = set()
        self.exported: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            self.imports.setdefault(bound, node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "__future__":
            return
        for alias in node.names:
            if alias.name != "*":
                self.imports.setdefault(alias.asname or alias.name, node)

    def visit_Name(self, node: ast.Name) -> None:
        self.used.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            self.used.add(root.id)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # Names used only inside string annotations, e.g. x: "Foo"
        if isinstance(node.value, str) and node.value.isidentifier():
            self.used.add(node.value)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                self.exported.update(e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str))
        self.generic_visit(node)

    def finish(self) -> None:
        if self.path.endswith("__init__.py"):
            return  # re-exports are normal in package __init__ files
        for name, node in self.imports.items():
            if name not in self.used and name not in self.exported:
                self.report(node, f"`{name}` imported but unused")


@register
class PrintCall(Rule):
    code = "AST004"
    name = "print-call"
    description = "`print()` left in library code; prefer logging."
    severity = Severity.INFO

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            self.report(node, "`print()` call; consider using `logging`")
        self.generic_visit(node)


@register
class CompareToSingleton(Rule):
    code = "AST005"
    name = "compare-to-singleton"
    description = "Use `is`/`is not` to compare with None, True or False."

    def visit_Compare(self, node: ast.Compare) -> None:
        operands = [node.left, *node.comparators]
        for i, op in enumerate(node.ops):
            if isinstance(op, (ast.Eq, ast.NotEq)):
                for side in (operands[i], operands[i + 1]):
                    if isinstance(side, ast.Constant) and side.value in (None, True, False) and type(side.value) is not int:
                        better = "is" if isinstance(op, ast.Eq) else "is not"
                        self.report(node, f"Comparison to `{side.value}` with `{'==' if isinstance(op, ast.Eq) else '!='}`; use `{better}`")
                        break
        self.generic_visit(node)


@register
class Complexity(Rule):
    code = "AST006"
    name = "high-complexity"
    description = "Function cyclomatic complexity exceeds the threshold (default 10)."
    _BRANCHES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.With, ast.AsyncWith,
                 ast.Assert, ast.IfExp, ast.comprehension, ast.match_case)

    def _check(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        limit = int(self.options.get("max_complexity", 10))
        score = complexity(node, self._BRANCHES)
        if score > limit:
            self.report(node, f"`{node.name}` has complexity {score} (max {limit})")
        self.generic_visit(node)

    visit_FunctionDef = visit_AsyncFunctionDef = _check


def complexity(func: ast.AST, branches: tuple) -> int:
    """McCabe-style complexity of one function, not counting nested functions."""
    score = 1
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, (*_FUNCS, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, branches):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
        stack.extend(ast.iter_child_nodes(node))
    return score


@register
class TooManyArguments(Rule):
    code = "AST007"
    name = "too-many-arguments"
    description = "Function takes more parameters than the threshold (default 6)."

    def _check(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        limit = int(self.options.get("max_args", 6))
        a = node.args
        params = [p.arg for p in (*a.posonlyargs, *a.args, *a.kwonlyargs)]
        if params and params[0] in ("self", "cls"):
            params = params[1:]
        if len(params) > limit:
            self.report(node, f"`{node.name}` takes {len(params)} arguments (max {limit})")
        self.generic_visit(node)

    visit_FunctionDef = visit_AsyncFunctionDef = _check
