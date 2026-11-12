"""Core engine: discovers files, parses them and runs rules."""
from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from ast_engine.models import Finding, Severity
from ast_engine.rules.base import Rule, all_rules

DEFAULT_EXCLUDES = {".git", ".hg", ".venv", "venv", "__pycache__", "build", "dist", ".tox", ".mypy_cache", "node_modules"}
_NOQA = re.compile(r"#\s*noqa(?::\s*(?P<codes>[A-Z0-9, ]+))?", re.IGNORECASE)


class Engine:
    def __init__(
        self,
        select: Iterable[str] | None = None,
        ignore: Iterable[str] | None = None,
        options: dict | None = None,
        rules: dict[str, type[Rule]] | None = None,
    ):
        available = rules if rules is not None else all_rules()
        select = {c.upper() for c in select} if select else None
        ignore = {c.upper() for c in ignore or ()}
        self.rules = {
            code: cls for code, cls in available.items()
            if (select is None or _matches(code, select)) and not _matches(code, ignore)
        }
        self.options = options or {}

    def check_source(self, source: str, path: str = "<string>") -> list[Finding]:
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            return [Finding(path, exc.lineno or 1, max((exc.offset or 1) - 1, 0), "AST000",
                            f"Syntax error: {exc.msg}", Severity.ERROR)]
        findings: list[Finding] = []
        for cls in self.rules.values():
            findings.extend(cls(path, source, tree, self.options).run())
        return sorted(_apply_noqa(findings, source.splitlines()))

    def check_file(self, path: str | Path) -> list[Finding]:
        path = Path(path)
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return [Finding(str(path), 1, 0, "AST000", f"Could not read file: {exc}", Severity.ERROR)]
        return self.check_source(source, str(path))

    def check_paths(self, paths: Iterable[str | Path]) -> list[Finding]:
        findings: list[Finding] = []
        for file in iter_python_files(paths):
            findings.extend(self.check_file(file))
        return findings


def iter_python_files(paths: Iterable[str | Path]) -> Iterator[Path]:
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*.py")):
                if not DEFAULT_EXCLUDES.intersection(f.relative_to(p).parts):
                    yield f


def _matches(code: str, patterns: set[str]) -> bool:
    """A pattern matches by prefix, so `AST00` selects AST001..AST009."""
    return any(code.startswith(p) for p in patterns)


def _apply_noqa(findings: list[Finding], lines: list[str]) -> Iterator[Finding]:
    for f in findings:
        line = lines[f.line - 1] if 0 < f.line <= len(lines) else ""
        m = _NOQA.search(line)
        if m:
            codes = m.group("codes")
            if codes is None or f.code in {c.strip().upper() for c in codes.split(",")}:
                continue
        yield f
