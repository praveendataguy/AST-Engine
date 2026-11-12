"""Rule base class and registry.

A rule is an ``ast.NodeVisitor`` subclass with a unique ``code``. Define
``visit_<NodeType>`` methods and call ``self.report(node, message)`` for each
problem. Decorate the class with ``@register`` to make the engine pick it up.
"""
from __future__ import annotations

import ast
from typing import ClassVar

from ast_engine.models import Finding, Severity

_REGISTRY: dict[str, type["Rule"]] = {}


class Rule(ast.NodeVisitor):
    code: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    severity: ClassVar[Severity] = Severity.WARNING

    def __init__(self, path: str, source: str, tree: ast.Module, options: dict | None = None):
        self.path = path
        self.source = source
        self.tree = tree
        self.options = options or {}
        self.findings: list[Finding] = []

    def run(self) -> list[Finding]:
        self.visit(self.tree)
        self.finish()
        return self.findings

    def finish(self) -> None:
        """Hook for rules that need to report after the whole tree is visited."""

    def report(self, node: ast.AST, message: str, severity: Severity | None = None) -> None:
        self.findings.append(
            Finding(
                path=self.path,
                line=getattr(node, "lineno", 1),
                col=getattr(node, "col_offset", 0),
                code=self.code,
                message=message,
                severity=severity or self.severity,
            )
        )


def register(cls: type[Rule]) -> type[Rule]:
    if not cls.code:
        raise ValueError(f"{cls.__name__} must define a rule code")
    if cls.code in _REGISTRY and _REGISTRY[cls.code] is not cls:
        raise ValueError(f"Duplicate rule code {cls.code}")
    _REGISTRY[cls.code] = cls
    return cls


def all_rules() -> dict[str, type[Rule]]:
    import ast_engine.rules.builtin  # noqa: AST003  (registers the built-in rules)

    return dict(sorted(_REGISTRY.items()))
